import { useRef, useState, useCallback } from 'react'

const TARGET_SAMPLE_RATE = 8000
const TTS_SAMPLE_RATE = 22050

function downsample(inputBuffer, inputRate, outputRate) {
  if (inputRate === outputRate) return inputBuffer
  const ratio = inputRate / outputRate
  const outputLength = Math.floor(inputBuffer.length / ratio)
  const output = new Float32Array(outputLength)
  for (let i = 0; i < outputLength; i++) {
    output[i] = inputBuffer[Math.floor(i * ratio)]
  }
  return output
}

function float32ToInt16(buffer) {
  const int16 = new Int16Array(buffer.length)
  for (let i = 0; i < buffer.length; i++) {
    const s = Math.max(-1, Math.min(1, buffer[i]))
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return int16
}

function int16ToBase64(int16Array) {
  const bytes = new Uint8Array(int16Array.buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i])
  }
  return btoa(binary)
}

function base64ToArrayBuffer(base64) {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i)
  }
  return bytes.buffer
}

export default function useVoiceAgent() {
  const [isConnected, setIsConnected] = useState(false)
  const [isCallActive, setIsCallActive] = useState(false)
  const [logs, setLogs] = useState([])
  const [callStatus, setCallStatus] = useState(null)

  const wsRef = useRef(null)
  const audioContextRef = useRef(null)
  const micStreamRef = useRef(null)
  const processorRef = useRef(null)
  const sourceRef = useRef(null)
  const streamSidRef = useRef(null)

  // Audio playback: accumulate MP3 chunks, decode via AudioContext, play via BufferSource
  const playbackContextRef = useRef(null)
  const mp3ChunksRef = useRef([])
  const flushTimerRef = useRef(null)
  const playbackQueueRef = useRef([])  // decoded AudioBuffers
  const isPlayingRef = useRef(false)
  const nextPlayTimeRef = useRef(0)
  const agentSpeakingRef = useRef(false)  // true from first media chunk to playback finish

  const addLog = useCallback((msg) => {
    const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setLogs(prev => [...prev, { time, msg }])
  }, [])

  const playNextChunk = useCallback(() => {
    const ctx = playbackContextRef.current
    if (!ctx || playbackQueueRef.current.length === 0) {
      isPlayingRef.current = false
      agentSpeakingRef.current = false  // Playback finished — unmute mic
      return
    }
    isPlayingRef.current = true

    const audioBuffer = playbackQueueRef.current.shift()
    const source = ctx.createBufferSource()
    source.buffer = audioBuffer
    source.connect(ctx.destination)

    const now = ctx.currentTime
    const startTime = Math.max(now, nextPlayTimeRef.current)
    source.start(startTime)
    nextPlayTimeRef.current = startTime + audioBuffer.duration

    source.onended = () => {
      playNextChunk()
    }
  }, [])

  const flushMp3Chunks = useCallback(() => {
    if (mp3ChunksRef.current.length === 0) return
    const ctx = playbackContextRef.current
    if (!ctx) return

    // Combine accumulated MP3 chunks into a single ArrayBuffer
    const totalLen = mp3ChunksRef.current.reduce((sum, c) => sum + c.byteLength, 0)
    const combined = new Uint8Array(totalLen)
    let offset = 0
    for (const chunk of mp3ChunksRef.current) {
      combined.set(new Uint8Array(chunk), offset)
      offset += chunk.byteLength
    }
    mp3ChunksRef.current = []

    // Decode MP3 to AudioBuffer using browser's native decoder
    // Need to copy the buffer because decodeAudioData detaches it
    const bufferCopy = combined.buffer.slice(0)
    ctx.decodeAudioData(bufferCopy).then(audioBuffer => {
      console.log(`[Audio] Decoded ${totalLen} bytes → ${audioBuffer.duration.toFixed(2)}s audio`)
      playbackQueueRef.current.push(audioBuffer)
      if (!isPlayingRef.current) {
        playNextChunk()
      }
    }).catch((err) => {
      console.warn(`[Audio] MP3 decode failed (${totalLen} bytes):`, err)
      // Fallback: try as raw PCM linear16
      try {
        const int16 = new Int16Array(combined.buffer)
        const float32 = new Float32Array(int16.length)
        for (let i = 0; i < int16.length; i++) {
          float32[i] = int16[i] / 32768
        }
        const buf = ctx.createBuffer(1, float32.length, TTS_SAMPLE_RATE)
        buf.getChannelData(0).set(float32)
        playbackQueueRef.current.push(buf)
        if (!isPlayingRef.current) {
          playNextChunk()
        }
      } catch (pcmErr) {
        console.error('[Audio] PCM fallback also failed:', pcmErr)
      }
    })
  }, [playNextChunk])

  const queueAudio = useCallback((base64Data) => {
    agentSpeakingRef.current = true  // Agent is speaking — mute mic
    const arrayBuffer = base64ToArrayBuffer(base64Data)
    mp3ChunksRef.current.push(arrayBuffer)

    // Flush after a short gap (500ms of no new chunks = fallback if tts_done missed)
    if (flushTimerRef.current) clearTimeout(flushTimerRef.current)
    flushTimerRef.current = setTimeout(() => {
      flushMp3Chunks()
    }, 500)
  }, [flushMp3Chunks])

  const clearAudioQueue = useCallback(() => {
    mp3ChunksRef.current = []
    playbackQueueRef.current = []
    if (flushTimerRef.current) clearTimeout(flushTimerRef.current)
    isPlayingRef.current = false
    nextPlayTimeRef.current = 0
    agentSpeakingRef.current = false
  }, [])

  const startMic = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      micStreamRef.current = stream

      const audioCtx = new AudioContext()
      audioContextRef.current = audioCtx

      const source = audioCtx.createMediaStreamSource(stream)
      sourceRef.current = source

      const processor = audioCtx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
        if (agentSpeakingRef.current) return  // Mute mic while agent audio is playing

        const inputData = e.inputBuffer.getChannelData(0)
        const downsampled = downsample(inputData, audioCtx.sampleRate, TARGET_SAMPLE_RATE)
        const int16 = float32ToInt16(downsampled)
        const base64 = int16ToBase64(int16)

        wsRef.current.send(JSON.stringify({
          event: 'media',
          media: { payload: base64 }
        }))
      }

      source.connect(processor)
      // Connect processor through a silent gain node — keeps processing alive
      // without playing raw mic audio through the speakers
      const silentGain = audioCtx.createGain()
      silentGain.gain.value = 0
      processor.connect(silentGain)
      silentGain.connect(audioCtx.destination)
      addLog('Microphone active')
    } catch (err) {
      addLog(`Mic error: ${err.message}`)
    }
  }, [addLog])

  const stopMic = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect()
      sourceRef.current = null
    }
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(t => t.stop())
      micStreamRef.current = null
    }
  }, [])

  const connect = useCallback((orderData) => {
    if (wsRef.current) return

    setCallStatus(null)
    setLogs([])
    addLog('Connecting to voice agent...')

    // Create playback AudioContext NOW — inside user gesture so Chrome allows it
    if (!playbackContextRef.current) {
      playbackContextRef.current = new AudioContext()
    }
    if (playbackContextRef.current.state === 'suspended') {
      playbackContextRef.current.resume()
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    const sid = `test-${Date.now()}`
    streamSidRef.current = sid

    ws.onopen = async () => {
      setIsConnected(true)
      addLog('WebSocket connected')

      // Send Exotel-style handshake
      ws.send(JSON.stringify({ event: 'connected' }))

      ws.send(JSON.stringify({
        event: 'start',
        stream_sid: sid,
        start: {
          call_sid: sid,
          from: '',
          to: '',
          stream_sid: sid,
          media_format: { encoding: 'audio/x-raw', sample_rate: 8000, bit_rate: 16 },
          ...orderData,
        }
      }))

      setIsCallActive(true)
      addLog('Call started — waiting for greeting...')

      // Start mic capture
      await startMic()
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.event === 'media') {
          const payload = data.media?.payload
          if (payload) {
            queueAudio(payload)
          }
        } else if (data.event === 'log') {
          addLog(`[Agent] ${data.message}`)
        } else if (data.event === 'end_call') {
          addLog(`Call ended: ${data.message}`)
          setCallStatus(data.status)
          setIsCallActive(false)
        } else if (data.event === 'tts_done') {
          // Server signals TTS segment complete — flush accumulated MP3 chunks now
          if (flushTimerRef.current) clearTimeout(flushTimerRef.current)
          flushMp3Chunks()
        } else if (data.event === 'clear') {
          clearAudioQueue()
        }
      } catch (err) {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      setIsCallActive(false)
      addLog('WebSocket disconnected')
      stopMic()
      wsRef.current = null
    }

    ws.onerror = (err) => {
      addLog('WebSocket error — is the backend running on :8080?')
    }
  }, [addLog, startMic, stopMic, queueAudio, clearAudioQueue, flushMp3Chunks])

  const disconnect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        event: 'stop',
        stop: { reason: 'user' }
      }))
      wsRef.current.close()
    }
    wsRef.current = null
    stopMic()
    clearAudioQueue()
    setIsConnected(false)
    setIsCallActive(false)
    addLog('Call ended by user')
  }, [addLog, stopMic, clearAudioQueue])

  return {
    isConnected,
    isCallActive,
    logs,
    callStatus,
    connect,
    disconnect,
  }
}

import { useState, useRef, useEffect } from 'react'
import useVoiceAgent from './useVoiceAgent'

const DEFAULT_ITEMS = [
  { name: 'Chicken Biryani', qty: 2, price: 250, variation: '' },
  { name: 'Paneer Butter Masala', qty: 1, price: 220, variation: '' },
]

const VARIATION_OPTIONS = ['', 'small', 'medium', 'large']

export default function App() {
  const { isConnected, isCallActive, logs, callStatus, connect, disconnect } = useVoiceAgent()
  const logEndRef = useRef(null)

  const [vendorName, setVendorName] = useState('Kavin')
  const [companyName, setCompanyName] = useState('Keeggi')
  const [orderId, setOrderId] = useState('ORD-2024-7891')
  const [items, setItems] = useState(DEFAULT_ITEMS)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const handleStart = () => {
    connect({
      vendor_name: vendorName,
      company_name: companyName,
      order_id: orderId,
      items: items.map(item => ({
        ...item,
        variation: item.variation || null,
      })),
    })
  }

  const updateItem = (index, field, value) => {
    setItems(prev => prev.map((item, i) =>
      i === index ? { ...item, [field]: (field === 'name' || field === 'variation') ? value : Number(value) } : item
    ))
  }

  const addItem = () => {
    setItems(prev => [...prev, { name: '', qty: 1, price: 0, variation: '' }])
  }

  const removeItem = (index) => {
    setItems(prev => prev.filter((_, i) => i !== index))
  }

  const total = items.reduce((sum, item) => sum + item.qty * item.price, 0)

  const statusColor = {
    ACCEPTED: '#22c55e',
    REJECTED: '#ef4444',
    CALLBACK_REQUESTED: '#f59e0b',
    NO_RESPONSE: '#6b7280',
    UNCLEAR_RESPONSE: '#8b5cf6',
  }

  return (
    <div className="app">
      <header>
        <h1>Voice Agent Tester</h1>
        <div className={`status-dot ${isConnected ? 'connected' : ''}`} />
        <span className="status-text">{isConnected ? 'Connected' : 'Disconnected'}</span>
      </header>

      <div className="main">
        <div className="panel left">
          <h2>Order Details</h2>

          <div className="form-group">
            <label>Vendor Name</label>
            <input value={vendorName} onChange={e => setVendorName(e.target.value)} disabled={isCallActive} />
          </div>

          <div className="form-group">
            <label>Company</label>
            <input value={companyName} onChange={e => setCompanyName(e.target.value)} disabled={isCallActive} />
          </div>

          <div className="form-group">
            <label>Order ID</label>
            <input value={orderId} onChange={e => setOrderId(e.target.value)} disabled={isCallActive} />
          </div>

          <h3>Items</h3>
          {items.map((item, i) => (
            <div key={i} className="item-row">
              <input
                className="item-name"
                placeholder="Item name"
                value={item.name}
                onChange={e => updateItem(i, 'name', e.target.value)}
                disabled={isCallActive}
              />
              <select
                className="item-variation"
                value={item.variation}
                onChange={e => updateItem(i, 'variation', e.target.value)}
                disabled={isCallActive}
              >
                {VARIATION_OPTIONS.map(v => (
                  <option key={v} value={v}>{v || '—'}</option>
                ))}
              </select>
              <input
                className="item-qty"
                type="number"
                min="1"
                value={item.qty}
                onChange={e => updateItem(i, 'qty', e.target.value)}
                disabled={isCallActive}
              />
              <input
                className="item-price"
                type="number"
                min="0"
                value={item.price}
                onChange={e => updateItem(i, 'price', e.target.value)}
                disabled={isCallActive}
              />
              {!isCallActive && items.length > 1 && (
                <button className="btn-remove" onClick={() => removeItem(i)}>x</button>
              )}
            </div>
          ))}

          {!isCallActive && (
            <button className="btn-add" onClick={addItem}>+ Add Item</button>
          )}

          <div className="total">Total: Rs. {total}</div>

          <div className="controls">
            {!isCallActive ? (
              <button className="btn-start" onClick={handleStart}>Start Call</button>
            ) : (
              <button className="btn-end" onClick={disconnect}>End Call</button>
            )}
          </div>

          {callStatus && (
            <div className="call-result" style={{ borderColor: statusColor[callStatus] || '#6b7280' }}>
              <span className="result-dot" style={{ background: statusColor[callStatus] || '#6b7280' }} />
              {callStatus}
            </div>
          )}
        </div>

        <div className="panel right">
          <h2>Live Logs</h2>
          <div className="log-container">
            {logs.length === 0 && <div className="log-empty">Start a call to see logs...</div>}
            {logs.map((log, i) => (
              <div key={i} className={`log-entry ${log.msg.startsWith('[Agent]') ? 'agent' : ''}`}>
                <span className="log-time">{log.time}</span>
                <span className="log-msg">{log.msg}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </div>
  )
}

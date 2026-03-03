# Fix: Agent Skips User Confirmation Before Ending Call

## Context

When the agent asks a confirmation question (e.g. "modify request போடலாமா?", "accept பண்றீங்க correct-ஆ?"), it should WAIT for the user to say YES before ending the call. Currently, the agent either:
- Ends immediately after asking the question (LLM combines confirmation ask + goodbye in one turn)
- Picks up noise/echo ("ம்.") and treats it as confirmation
- Silence timeout fires and ends the call before user can respond

This affects ALL three flows: accept, reject, and modify.

## Root Cause

1. **No unified confirmation gate**: The pending flag mechanism (`_rejection_pending`, `_modification_pending`) is inconsistent — acceptance has NO pending flag at all
2. **LLM skips steps**: The LLM sometimes returns a terminal status (MODIFIED/ACCEPTED/REJECTED) on the SAME turn it asks the confirmation question, so the code ends the call immediately
3. **Noise triggers confirmation**: Short transcripts like "ம்." pass through and the LLM treats them as "yes"

## Solution: Unified `_confirmation_pending` State

Replace the separate `_rejection_pending` and `_modification_pending` flags with a single `_confirmation_pending` that gates ALL terminal statuses behind user confirmation.

### Changes to `agent.py`

**1. Replace pending flags with unified state (constructor, ~line 80-82):**

Remove:
```python
self._rejection_pending = False
self._modification_pending = False
```

Add:
```python
self._confirmation_pending = None  # None or expected status: "ACCEPTED", "REJECTED", "MODIFIED"
```

Keep `_rejection_reason` and `_modification_reason` as they are.

**2. Rewrite terminal status handling in `_on_transcript` (~lines 323-365):**

New logic:
```python
terminal = self._extract_terminal_status(status)

if terminal:
    if self._confirmation_pending == terminal:
        # User confirmed — agent already asked, now end the call
        # Extract reason if applicable
        if terminal == "REJECTED":
            new_reason = self._extract_reason_from_status(status) or text.strip()
            if new_reason and new_reason not in self._rejection_reason:
                self._rejection_reason = (self._rejection_reason + " | " + new_reason) if self._rejection_reason else new_reason
        elif terminal == "MODIFIED":
            new_reason = self._extract_reason_from_status(status) or text.strip()
            if new_reason and new_reason not in self._modification_reason:
                self._modification_reason = (self._modification_reason + " | " + new_reason) if self._modification_reason else new_reason
        await self._send_webhook(terminal)
        await self._finish_call(terminal)
    elif self._speak_is_question(speak_text):
        # Agent is asking a confirmation question — set pending, wait for user
        self._confirmation_pending = terminal
        # Extract reason from status if present (for reject/modify)
        if terminal == "REJECTED":
            reason = self._extract_reason_from_status(status)
            if reason:
                self._rejection_reason = reason
        elif terminal == "MODIFIED":
            reason = self._extract_reason_from_status(status)
            if reason:
                self._modification_reason = reason
        await self._send_log(f"Confirmation pending for {terminal} — waiting for user YES")
    else:
        # Terminal status with no question — end call directly
        await self._send_webhook(terminal)
        await self._finish_call(terminal)
elif self._confirmation_pending:
    # LLM didn't return terminal but we're waiting for confirmation
    # Check if this is a clear yes/no from the user
    # The LLM should handle this — if user said yes, LLM returns terminal next time
    # If LLM returned CONFIRMING, just keep waiting
    pass
```

**3. Update silence timeout handler (~lines 647-665):**

Replace the separate `_rejection_pending` and `_modification_pending` checks with:
```python
if self._confirmation_pending:
    await self._send_log(f"Silence after confirmation question — ending with {self._confirmation_pending}")
    goodbye = "சரி... நன்றி."
    self._last_agent_text = goodbye
    await self._speak(goodbye)
    await self._send_webhook(self._confirmation_pending)
    await self._finish_call(self._confirmation_pending)
    return
```

**4. Reset confirmation on user speech (`_on_transcript` at the top, ~line 291):**

Do NOT reset `_confirmation_pending` when user speaks — we want to keep it until the LLM confirms the terminal status. The `_silence_prompts_sent` reset stays.

## Files to Change

| File | Changes |
|------|---------|
| `agent.py` | Replace `_rejection_pending` + `_modification_pending` with `_confirmation_pending`. Rewrite terminal status handling block. Update silence timeout handler. |

No changes needed in `config.py` — the system prompt already has the correct steps.

## Verification

1. **Modify flow**: Say "modify பண்ணணும்" → agent asks why → give reason → agent repeats reason + "modify request போடலாமா?" → say "ஆமா" → agent says "done, thanks" → call ends
2. **Accept flow**: Say "ஓகே" → agent asks "accept பண்றீங்க correct-ஆ?" → say "ஆமா" → agent says "confirm பண்ணிட்டேன்" → call ends
3. **Reject flow**: Say "வேணாம்" → agent asks why → give reason → agent confirms reason → say "ஆமா" → agent ends
4. **Silence test**: If user stays silent after confirmation question → silence timeout should still end the call after 7s
5. **Noise test**: Short noise like "ம்." should NOT trigger premature call end

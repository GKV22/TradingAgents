import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './Analysis.css'

function fixMarkdown(md: string): string {
  const lines = md.split('\n')
  const out: string[] = []

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i]
    let trimmed = line.trim()

    // Convert tab-separated rows to GFM pipe tables (LLMs sometimes use TSV)
    if (!trimmed.startsWith('|') && trimmed.includes('\t')) {
      const parts = trimmed.split('\t').map(s => s.trim())
      if (parts.length >= 2) {
        line = '| ' + parts.join(' | ') + ' |'
        trimmed = line.trim()
      }
    }

    const isTableRow = trimmed.startsWith('|') && trimmed.split('|').length > 2
    const isSepRow = isTableRow && /^[\|\-\s:]+$/.test(trimmed)

    // Fix missing closing pipe on table rows
    if (isTableRow && !trimmed.endsWith('|')) {
      line = line.trimEnd() + ' |'
    }

    out.push(line)

    // Inject missing separator row after table header (first row of a table)
    if (isTableRow && !isSepRow) {
      const prevLine = (out[out.length - 2] ?? '').trim()
      const prevIsTableRow = prevLine.startsWith('|') && prevLine.split('|').length > 2
      const nextLine = lines[i + 1] ?? ''
      const nextTrimmed = nextLine.trim()
      // Skip blank lines when looking for the separator
      const nextContent = nextTrimmed || (lines[i + 2] ?? '').trim()
      const nextIsSep = nextContent.startsWith('|') && /^[\|\-\s:]+$/.test(nextContent)

      if (!prevIsTableRow && !nextIsSep) {
        const cols = line.trim().split('|').length - 2
        if (cols > 0) out.push('|' + ' --- |'.repeat(cols))
      }
    }
  }

  return out.join('\n')
}

const AGENT_PIPELINE = [
  'Market Analyst',
  'Social Analyst',
  'News Analyst',
  'Fundamentals Analyst',
  'Bull Researcher',
  'Bear Researcher',
  'Research Manager',
  'Trader',
  'Aggressive Analyst',
  'Conservative Analyst',
  'Neutral Analyst',
  'Portfolio Manager',
  'Report Critic',
]

type AgentStatus = 'pending' | 'in_progress' | 'completed'

interface ReportSection {
  section: string
  title: string
  content: string
}

interface Stats {
  tokens_in?: number
  tokens_out?: number
  total_cost?: number
  llm_calls?: number
}

function fmt(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export default function Analysis() {
  const today = new Date().toISOString().split('T')[0]
  const [ticker, setTicker] = useState('')
  const [date, setDate] = useState(today)
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)
  const [statuses, setStatuses] = useState<Record<string, AgentStatus>>({})
  const [sections, setSections] = useState<ReportSection[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const runLabel = useRef('')

  const stopTimer = () => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null }
  }

  useEffect(() => () => stopTimer(), [])

  const handleEvent = (ev: Record<string, unknown>) => {
    const t = ev.type as string
    if (t === 'agent_status') {
      setStatuses(prev => ({ ...prev, [ev.agent as string]: ev.status as AgentStatus }))
    } else if (t === 'report_section') {
      setSections(prev => {
        if (prev.some(s => s.section === ev.section)) return prev
        setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 60)
        return [...prev, {
          section: ev.section as string,
          title: ev.title as string,
          content: ev.content as string,
        }]
      })
    } else if (t === 'stats') {
      setStats(ev as unknown as Stats)
    } else if (t === 'error') {
      setError(ev.message as string)
    }
  }

  const start = async () => {
    if (!ticker.trim()) { setError('Enter a ticker symbol'); return }
    const sym = ticker.trim().toUpperCase()
    setError(null); setSections([]); setStatuses({}); setStats(null)
    setDone(false); setElapsed(0); setRunning(true)
    runLabel.current = `${sym} — ${date}`
    timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)

    const abort = new AbortController()
    abortRef.current = abort

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: sym, date }),
        signal: abort.signal,
      })
      if (!res.ok) throw new Error(await res.text() || res.statusText)

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done: streamDone, value } = await reader.read()
        if (streamDone) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const ev = JSON.parse(line.slice(6)) as Record<string, unknown>
            handleEvent(ev)
            if (ev.type === 'complete' || ev.type === 'error') {
              setStatuses(prev => {
                const next = { ...prev }
                for (const k of Object.keys(next)) {
                  if (next[k] === 'in_progress') next[k] = 'completed'
                }
                return next
              })
              stopTimer(); setRunning(false); setDone(true); return
            }
          } catch { /* ignore malformed line */ }
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') setError(String(e))
    } finally {
      stopTimer(); setRunning(false)
    }
  }

  const stop = async () => {
    abortRef.current?.abort()
    await fetch('/api/stop', { method: 'POST' }).catch(() => {})
    stopTimer(); setRunning(false)
  }

  const activeAgent = AGENT_PIPELINE.find(a => statuses[a] === 'in_progress')
  const completedCount = AGENT_PIPELINE.filter(a => statuses[a] === 'completed').length

  return (
    <div className="analysis">
      {/* Controls */}
      <div className="card analysis-form no-print">
        <div className="form-row">
          <div className="field">
            <label>Ticker</label>
            <input
              type="text"
              placeholder="AAPL"
              value={ticker}
              onChange={e => setTicker(e.target.value.toUpperCase())}
              disabled={running}
              onKeyDown={e => { if (e.key === 'Enter') start() }}
            />
          </div>
          <div className="field">
            <label>Analysis Date</label>
            <input type="date" value={date} max={today}
              onChange={e => setDate(e.target.value)} disabled={running} />
          </div>
          <div className="form-actions">
            {!running
              ? <button className="primary" onClick={start}>Run Analysis</button>
              : <button className="stop-btn" onClick={stop}>Stop</button>
            }
            {sections.length > 0 && (
              <button className="print-btn" onClick={() => {
                const prev = document.title
                document.title = `TradingAgents - ${runLabel.current}`
                window.print()
                document.title = prev
              }}>
                Print Report
              </button>
            )}
          </div>
        </div>
        {error && <div className="err-msg" style={{ marginTop: '0.75rem' }}>{error}</div>}
      </div>

      {/* Status panel */}
      {(running || done) && (
        <div className="card status-panel no-print">
          <div className="status-header">
            <div className="status-left">
              {running && <span className="spinner" />}
              <span className="status-label">
                {running
                  ? (activeAgent ? activeAgent : 'Starting…')
                  : `Complete — ${completedCount} agents`}
              </span>
            </div>
            <div className="status-right">
              <span className="timer">{fmt(elapsed)}</span>
              {stats?.total_cost != null && (
                <span className="cost">${Number(stats.total_cost).toFixed(4)}</span>
              )}
            </div>
          </div>

          <div className="agent-pipeline">
            {AGENT_PIPELINE.map(agent => {
              const status = statuses[agent] ?? 'pending'
              return (
                <div key={agent} className={`agent-chip status-${status}`}>
                  <span className="agent-dot" />
                  <span>{agent}</span>
                </div>
              )
            })}
          </div>

          {stats && (
            <div className="stats-bar">
              <span>LLM calls: {stats.llm_calls ?? 0}</span>
              <span>Tokens in: {(stats.tokens_in ?? 0).toLocaleString()}</span>
              <span>Tokens out: {(stats.tokens_out ?? 0).toLocaleString()}</span>
            </div>
          )}
        </div>
      )}

      {/* Print header — only visible when printing */}
      {sections.length > 0 && (
        <div className="print-header print-only">
          <h1 className="print-title">{runLabel.current}</h1>
          <p className="print-meta">Generated {new Date().toLocaleString()} · Duration {fmt(elapsed)}</p>
          <hr />
        </div>
      )}

      {/* Progressive report sections */}
      <div className="sections-list">
        {sections.map(sec => (
          <div key={sec.section} className="card report-section">
            <div className="section-title">{sec.title}</div>
            <div className="section-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{fixMarkdown(sec.content)}</ReactMarkdown>
            </div>
          </div>
        ))}
      </div>

      <div ref={bottomRef} />
    </div>
  )
}

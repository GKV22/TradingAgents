import { useState } from 'react'
import Analysis from './pages/Analysis'
import Policies from './pages/Policies'
import Settings from './pages/Settings'
import './App.css'

type Tab = 'analysis' | 'policies' | 'settings'

export default function App() {
  const [tab, setTab] = useState<Tab>('analysis')

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <h1 className="logo">TradingAgents</h1>
          <nav className="tabs">
            <button
              className={`tab-btn ${tab === 'analysis' ? 'active' : ''}`}
              onClick={() => setTab('analysis')}
            >
              Analysis
            </button>
            <button
              className={`tab-btn ${tab === 'policies' ? 'active' : ''}`}
              onClick={() => setTab('policies')}
            >
              Policies
            </button>
            <button
              className={`tab-btn ${tab === 'settings' ? 'active' : ''}`}
              onClick={() => setTab('settings')}
            >
              Settings
            </button>
          </nav>
        </div>
      </header>

      <main className="content">
        <div style={{ display: tab === 'analysis' ? 'contents' : 'none' }}><Analysis /></div>
        {tab === 'policies' && <Policies />}
        {tab === 'settings' && <Settings />}
      </main>
    </div>
  )
}

import { useState } from 'react'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts'

// ─── Types ────────────────────────────────────────────────────────────────────

interface DNAValues {
  micro: number
  macro: number
  mystico: number
}

interface Game {
  id: number
  title: string
  year: number
  platforms: string[]
  challenge: DNAValues
  reward: DNAValues
  tags: string[]
  dnaScore: number
  color: string
  abbr: string
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const GAMES: Game[] = [
  {
    id: 1,
    title: 'Apex Legends',
    year: 2019,
    platforms: ['windows', 'playstation', 'xbox'],
    challenge: { micro: 9.1, macro: 4.2, mystico: 2.8 },
    reward: { micro: 8.6, macro: 5.1, mystico: 3.4 },
    tags: ['Battle Royale', 'Intense Execution', 'Team Play'],
    dnaScore: 7.2,
    color: '#e05c2c',
    abbr: 'APX',
  },
  {
    id: 2,
    title: 'Civilization VI',
    year: 2016,
    platforms: ['windows', 'playstation', 'xbox'],
    challenge: { micro: 2.3, macro: 9.4, mystico: 5.7 },
    reward: { micro: 3.1, macro: 9.2, mystico: 6.8 },
    tags: ['Deep Strategy', '4X Empire', 'Long-form'],
    dnaScore: 8.4,
    color: '#3d6bb3',
    abbr: 'CIV',
  },
  {
    id: 3,
    title: 'Elden Ring',
    year: 2022,
    platforms: ['windows', 'playstation', 'xbox'],
    challenge: { micro: 8.7, macro: 6.3, mystico: 9.1 },
    reward: { micro: 7.9, macro: 7.2, mystico: 9.5 },
    tags: ['Souls-like', 'Open World', 'Lore-Dense'],
    dnaScore: 9.1,
    color: '#c4a44a',
    abbr: 'ELD',
  },
  {
    id: 4,
    title: 'Counter-Strike 2',
    year: 2023,
    platforms: ['windows'],
    challenge: { micro: 9.8, macro: 5.6, mystico: 1.2 },
    reward: { micro: 9.4, macro: 4.9, mystico: 1.8 },
    tags: ['Tactical FPS', 'Precision', 'Competitive'],
    dnaScore: 6.8,
    color: '#e5872b',
    abbr: 'CS2',
  },
  {
    id: 5,
    title: 'Hollow Knight',
    year: 2017,
    platforms: ['windows', 'playstation', 'xbox'],
    challenge: { micro: 7.2, macro: 5.8, mystico: 8.4 },
    reward: { micro: 6.9, macro: 6.2, mystico: 9.0 },
    tags: ['Metroidvania', 'Atmospheric', 'Precise'],
    dnaScore: 8.7,
    color: '#7ba3d4',
    abbr: 'HLK',
  },
  {
    id: 6,
    title: 'Factorio',
    year: 2020,
    platforms: ['windows'],
    challenge: { micro: 3.4, macro: 9.8, mystico: 4.1 },
    reward: { micro: 4.2, macro: 9.6, mystico: 5.3 },
    tags: ['Automation', 'Systems Thinking', 'Sandbox'],
    dnaScore: 8.9,
    color: '#ff7c00',
    abbr: 'FAC',
  },
  {
    id: 7,
    title: 'Dark Souls III',
    year: 2016,
    platforms: ['windows', 'playstation', 'xbox'],
    challenge: { micro: 8.9, macro: 6.7, mystico: 7.8 },
    reward: { micro: 8.1, macro: 6.4, mystico: 8.6 },
    tags: ['Punishing', 'Dark Fantasy', 'Mastery'],
    dnaScore: 8.8,
    color: '#6b3a7d',
    abbr: 'DS3',
  },
  {
    id: 8,
    title: 'Stardew Valley',
    year: 2016,
    platforms: ['windows', 'playstation', 'xbox'],
    challenge: { micro: 1.8, macro: 4.3, mystico: 7.2 },
    reward: { micro: 2.4, macro: 5.1, mystico: 8.9 },
    tags: ['Cozy Sim', 'Slow Burn', 'Narrative'],
    dnaScore: 7.6,
    color: '#5aaa5f',
    abbr: 'SDV',
  },
]

// ─── Radar chart data builder ─────────────────────────────────────────────────

function buildRadarData(game: Game) {
  return [
    { axis: 'Micro', challenge: game.challenge.micro, reward: game.reward.micro },
    { axis: 'Macro', challenge: game.challenge.macro, reward: game.reward.macro },
    { axis: 'Mystico', challenge: game.challenge.mystico, reward: game.reward.mystico },
  ]
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function WindowsIcon() {
  return (
    <svg className="platform-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-13.051-1.8" />
    </svg>
  )
}

function PlayStationIcon() {
  return (
    <svg className="platform-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M8.984 2.596v14.047l3.69 1.172V6.333c0-.56.234-.84.609-.714.487.159.58.619.58 1.178v4.638c1.719.91 3.064.068 3.064-2.743 0-2.88-.974-4.085-3.834-5.096-1.07-.37-2.744-.804-3.109-1zm6.857 13.527c-1.773.535-3.644.32-5.176-.48l-.004 2.45c1.687.95 4.444 1.082 6.734.086 2.53-1.09 3.02-3.042 2.29-4.85-.678-1.713-2.256-2.668-5.304-3.567v2.25c1.707.555 2.55 1.19 2.676 2.24.128 1.06-.465 1.623-1.212 1.87zM3 20.894l4.668 1.485V19.91L3 18.43z" />
    </svg>
  )
}

function XboxIcon() {
  return (
    <svg className="platform-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <path d="M4.102 6.197C2.07 8.197 1 10.653 1 12.147c0 2.596 1.638 5.773 3.945 7.474.94.692 1.017.628 3.154-1.645C9.805 16.147 11.267 14.4 12 14.4s2.195 1.747 3.901 3.576c2.137 2.273 2.214 2.337 3.154 1.645C21.362 17.92 23 14.743 23 12.147c0-1.494-1.07-3.95-3.102-5.95C17.803 4.113 15.363 3 12 3S6.197 4.113 4.102 6.197zm7.898-.447c-1.278 1.318-4.364 5.484-4.364 5.484s-.846-3.247-.098-5.036c.403-.97.94-1.517 1.678-1.747C10.104 4.158 11.43 5.283 12 5.75zm3.288 3.688c0-1.66-.657-3.163-1.715-4.265-.37-.39-.626-.748-.573-.748.052 0 .573.162 1.15.36.578.198 1.432.63 1.9 1.06 1.205 1.104 1.615 3.39.908 5.11-.136.332-.252.532-.258.444-.006-.088-.002-.95-.004-1.96h-.408z" />
    </svg>
  )
}

function PlatformIcons({ platforms }: { platforms: string[] }) {
  return (
    <div className="flex items-center gap-1.5">
      {platforms.includes('windows') && <WindowsIcon />}
      {platforms.includes('playstation') && <PlayStationIcon />}
      {platforms.includes('xbox') && <XboxIcon />}
    </div>
  )
}

function GameRadarChart({ game }: { game: Game }) {
  const data = buildRadarData(game)
  return (
    <div style={{ width: 110, height: 90, flexShrink: 0 }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} margin={{ top: 4, right: 14, bottom: 4, left: 14 }}>
          <PolarGrid
            stroke="#21262d"
            strokeWidth={1}
            gridType="polygon"
          />
          <PolarAngleAxis
            dataKey="axis"
            tick={{ fill: '#484f58', fontSize: 8, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}
            tickLine={false}
          />
          <Radar
            name="Challenge"
            dataKey="challenge"
            stroke="#58a6ff"
            fill="#58a6ff"
            fillOpacity={0.18}
            strokeWidth={1.5}
            dot={false}
          />
          <Radar
            name="Reward"
            dataKey="reward"
            stroke="#3fb950"
            fill="#3fb950"
            fillOpacity={0.15}
            strokeWidth={1.5}
            dot={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

interface SliderRowProps {
  label: string
  value: number
  onChange: (v: number) => void
  color: 'blue' | 'green' | 'purple'
}

function SliderRow({ label, value, onChange, color }: SliderRowProps) {
  const pct = ((value - 1) / 9) * 100
  const colorClass = `slider-track-${color}`
  const thumbClass = color === 'blue' ? '' : color
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: '#8b949e', fontFamily: 'JetBrains Mono, monospace' }}>{label}</span>
        <span
          style={{
            fontSize: 10,
            fontFamily: 'JetBrains Mono, monospace',
            fontWeight: 700,
            color: color === 'blue' ? '#58a6ff' : color === 'green' ? '#3fb950' : '#bc8cff',
          }}
        >
          {value.toFixed(0)}
        </span>
      </div>
      <input
        type="range"
        min={1}
        max={10}
        step={1}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className={`${colorClass} ${thumbClass}`}
        style={{ ['--pct' as string]: `${pct}%` }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
        {[1, 3, 5, 7, 10].map(n => (
          <span key={n} style={{ fontSize: 9, color: '#30363d', fontFamily: 'JetBrains Mono, monospace' }}>{n}</span>
        ))}
      </div>
    </div>
  )
}

function GameCard({ game }: { game: Game }) {
  return (
    <div className="game-card">
      {/* Thumbnail */}
      <div
        style={{
          width: 48,
          height: 64,
          borderRadius: 4,
          background: game.color + '22',
          border: `1px solid ${game.color}44`,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 11,
          fontWeight: 700,
          color: game.color,
          letterSpacing: '0.05em',
        }}
      >
        {game.abbr}
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#e6edf3', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {game.title}
          </span>
          <span className="score-badge">{game.dnaScore.toFixed(1)}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: '#484f58', fontFamily: 'JetBrains Mono, monospace' }}>{game.year}</span>
          <PlatformIcons platforms={game.platforms} />
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
          {game.tags.map(tag => (
            <span key={tag} className="tag">{tag}</span>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn-primary">View Details</button>
          <button className="btn-ghost">Compare</button>
        </div>
      </div>

      {/* DNA Radar */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, flexShrink: 0 }}>
        <div style={{ fontSize: 9, color: '#484f58', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          DNA
        </div>
        <GameRadarChart game={game} />
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 9, color: '#484f58' }}>
            <span style={{ width: 8, height: 2, background: '#58a6ff', display: 'inline-block', borderRadius: 1 }} />
            Chal
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 9, color: '#484f58' }}>
            <span style={{ width: 8, height: 2, background: '#3fb950', display: 'inline-block', borderRadius: 1 }} />
            Rew
          </span>
        </div>
      </div>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [query, setQuery] = useState('')
  const [sortTab, setSortTab] = useState('relevancy')
  const [activeNav, setActiveNav] = useState('database')

  // Challenge filters
  const [chMicro, setChMicro] = useState(5)
  const [chMacro, setChMacro] = useState(5)
  const [chMystico, setChMystico] = useState(5)

  // Reward filters
  const [rwMicro, setRwMicro] = useState(5)
  const [rwMacro, setRwMacro] = useState(5)
  const [rwMystico, setRwMystico] = useState(5)

  // Standard filters
  const [releaseYear, setReleaseYear] = useState(2020)
  const [popularity, setPopularity] = useState(7)
  const [platforms, setPlatforms] = useState({ windows: true, playstation: true, xbox: true })

  const togglePlatform = (key: keyof typeof platforms) => {
    setPlatforms(p => ({ ...p, [key]: !p[key] }))
  }

  const filteredGames = GAMES.filter(g => {
    if (query && !g.title.toLowerCase().includes(query.toLowerCase())) return false
    if (!platforms.windows && !platforms.playstation && !platforms.xbox) return true
    const hasPlatform =
      (platforms.windows && g.platforms.includes('windows')) ||
      (platforms.playstation && g.platforms.includes('playstation')) ||
      (platforms.xbox && g.platforms.includes('xbox'))
    return hasPlatform
  })

  const sorted = [...filteredGames].sort((a, b) => {
    if (sortTab === 'release') return b.year - a.year
    if (sortTab === 'dna') return b.dnaScore - a.dnaScore
    return b.dnaScore - a.dnaScore
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: '#0d1117' }}>

      {/* ── NAV ── */}
      <nav
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          height: 44,
          background: '#161b22',
          borderBottom: '1px solid #21262d',
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          padding: '0 16px',
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 20, flexShrink: 0 }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" stroke="#58a6ff" strokeWidth="1.5"/>
            <path d="M12 6v6M9 9l6 6M15 9l-6 6" stroke="#58a6ff" strokeWidth="1.5" strokeLinecap="round"/>
            <circle cx="12" cy="12" r="2" fill="#3fb950"/>
          </svg>
          <span style={{ fontWeight: 700, fontSize: 15, color: '#e6edf3', letterSpacing: '-0.01em' }}>
            Game<span style={{ color: '#58a6ff' }}>DNA</span>
          </span>
        </div>

        {/* Search */}
        <div style={{ flex: 1, maxWidth: 460, margin: '0 auto', position: 'relative' }}>
          <svg
            style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', width: 13, height: 13, fill: '#484f58' }}
            viewBox="0 0 24 24"
          >
            <path d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" stroke="#484f58" strokeWidth="2" fill="none" strokeLinecap="round"/>
          </svg>
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search for games, mechanics, DNA..."
            style={{
              width: '100%',
              height: 30,
              background: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: 6,
              paddingLeft: 30,
              paddingRight: 12,
              fontSize: 12,
              color: '#e6edf3',
              outline: 'none',
              fontFamily: 'Inter, sans-serif',
            }}
            onFocus={e => { e.target.style.borderColor = '#58a6ff'; e.target.style.boxShadow = '0 0 0 3px rgba(88,166,255,0.12)' }}
            onBlur={e => { e.target.style.borderColor = '#30363d'; e.target.style.boxShadow = 'none' }}
          />
        </div>

        {/* Nav links */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, marginLeft: 16, flexShrink: 0 }}>
          {[
            { key: 'database', label: 'Database' },
            { key: 'analyze', label: 'Analyze' },
            { key: 'explore', label: 'Explore' },
          ].map(({ key, label }) => (
            <button
              key={key}
              className={`nav-link ${activeNav === key ? 'active' : ''}`}
              onClick={() => setActiveNav(key)}
              style={{ background: 'none', border: 'none', cursor: 'pointer' }}
            >
              {label}
            </button>
          ))}

          {/* Profile */}
          <div
            style={{
              marginLeft: 8,
              width: 28,
              height: 28,
              borderRadius: '50%',
              background: '#21262d',
              border: '1px solid #30363d',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="8" r="4" stroke="#8b949e" strokeWidth="1.5"/>
              <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" stroke="#8b949e" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
        </div>
      </nav>

      {/* ── BODY ── */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ── SIDEBAR ── */}
        <aside
          style={{
            width: 268,
            flexShrink: 0,
            borderRight: '1px solid #21262d',
            overflowY: 'auto',
            padding: '16px 14px',
            background: '#0d1117',
          }}
        >
          {/* Intro card */}
          <div
            style={{
              background: '#161b22',
              border: '1px solid #21262d',
              borderRadius: 6,
              padding: '12px 14px',
              marginBottom: 16,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 700, color: '#e6edf3', lineHeight: 1.4, marginBottom: 8 }}>
              Uncover Your Perfect Game.{' '}
              <span style={{ color: '#58a6ff' }}>Beyond Genre.</span>
            </div>
            <div style={{ fontSize: 11, color: '#8b949e', lineHeight: 1.6 }}>
              GameDNA classifies games by their actual play mechanics — not marketing labels. Every game gets a DNA profile scored across three axes:
            </div>
            <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                { label: 'Micro', color: '#58a6ff', desc: 'Moment-to-moment execution & reflex' },
                { label: 'Macro', color: '#3fb950', desc: 'Long-term planning & systems' },
                { label: 'Mystico', color: '#bc8cff', desc: 'Narrative depth & emergent wonder' },
              ].map(({ label, color, desc }) => (
                <div key={label} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <span
                    style={{
                      marginTop: 2,
                      fontSize: 9,
                      fontWeight: 700,
                      color,
                      fontFamily: 'JetBrains Mono, monospace',
                      letterSpacing: '0.06em',
                      flexShrink: 0,
                      minWidth: 46,
                    }}
                  >
                    {label.toUpperCase()}
                  </span>
                  <span style={{ fontSize: 10, color: '#8b949e', lineHeight: 1.5 }}>{desc}</span>
                </div>
              ))}
            </div>
          </div>

          {/* DNA Filters */}
          <div
            style={{
              background: '#161b22',
              border: '1px solid #21262d',
              borderRadius: 6,
              padding: '12px 14px',
              marginBottom: 12,
            }}
          >
            <div className="filter-label">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" stroke="#58a6ff" strokeWidth="2"/>
                <circle cx="12" cy="12" r="3" fill="#58a6ff"/>
              </svg>
              DNA Filters
            </div>

            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: '#58a6ff', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 16, height: 1, background: '#58a6ff', display: 'inline-block' }} />
                Challenge
              </div>
              <SliderRow label="Micro" value={chMicro} onChange={setChMicro} color="blue" />
              <SliderRow label="Macro" value={chMacro} onChange={setChMacro} color="blue" />
              <SliderRow label="Mystico" value={chMystico} onChange={setChMystico} color="blue" />
            </div>

            <div style={{ borderTop: '1px solid #21262d', paddingTop: 10 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: '#3fb950', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 16, height: 1, background: '#3fb950', display: 'inline-block' }} />
                Reward
              </div>
              <SliderRow label="Micro" value={rwMicro} onChange={setRwMicro} color="green" />
              <SliderRow label="Macro" value={rwMacro} onChange={setRwMacro} color="green" />
              <SliderRow label="Mystico" value={rwMystico} onChange={setRwMystico} color="green" />
            </div>
          </div>

          {/* Standard Filters */}
          <div
            style={{
              background: '#161b22',
              border: '1px solid #21262d',
              borderRadius: 6,
              padding: '12px 14px',
            }}
          >
            <div className="filter-label">Standard Filters</div>

            {/* Platform */}
            <div className="filter-section">
              <div style={{ fontSize: 10, color: '#8b949e', fontWeight: 600, marginBottom: 7, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Platform
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {[
                  { key: 'windows' as const, label: 'Windows / PC' },
                  { key: 'playstation' as const, label: 'PlayStation' },
                  { key: 'xbox' as const, label: 'Xbox' },
                ].map(({ key, label }) => (
                  <label
                    key={key}
                    style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', fontSize: 11, color: '#8b949e' }}
                  >
                    <input
                      type="checkbox"
                      checked={platforms[key]}
                      onChange={() => togglePlatform(key)}
                      style={{ accentColor: '#58a6ff', width: 12, height: 12 }}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>

            {/* Release Year */}
            <div className="filter-section">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 7 }}>
                <span style={{ fontSize: 10, color: '#8b949e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Release Year
                </span>
                <span style={{ fontSize: 10, color: '#58a6ff', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 }}>
                  ≥{releaseYear}
                </span>
              </div>
              <input
                type="range"
                min={2000}
                max={2024}
                value={releaseYear}
                onChange={e => setReleaseYear(Number(e.target.value))}
                className="slider-track-blue"
                style={{ ['--pct' as string]: `${((releaseYear - 2000) / 24) * 100}%` }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
                <span style={{ fontSize: 9, color: '#30363d', fontFamily: 'JetBrains Mono, monospace' }}>2000</span>
                <span style={{ fontSize: 9, color: '#30363d', fontFamily: 'JetBrains Mono, monospace' }}>2024</span>
              </div>
            </div>

            {/* Popularity */}
            <div className="filter-section" style={{ marginBottom: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 7 }}>
                <span style={{ fontSize: 10, color: '#8b949e', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Popularity
                </span>
                <span style={{ fontSize: 10, color: '#bc8cff', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 }}>
                  {popularity}/10
                </span>
              </div>
              <input
                type="range"
                min={1}
                max={10}
                value={popularity}
                onChange={e => setPopularity(Number(e.target.value))}
                className="slider-track-purple purple"
                style={{ ['--pct' as string]: `${((popularity - 1) / 9) * 100}%` }}
              />
            </div>
          </div>

          {/* Legend */}
          <div style={{ marginTop: 12, padding: '8px 10px', background: '#161b22', border: '1px solid #21262d', borderRadius: 6 }}>
            <div style={{ fontSize: 9, color: '#484f58', fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, letterSpacing: '0.06em', marginBottom: 6, textTransform: 'uppercase' }}>
              Chart Legend
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {[
                { color: '#58a6ff', label: 'Challenge DNA' },
                { color: '#3fb950', label: 'Reward DNA' },
              ].map(({ color, label }) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 16, height: 2, background: color, borderRadius: 1, flexShrink: 0 }} />
                  <span style={{ fontSize: 10, color: '#8b949e' }}>{label}</span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* ── MAIN PANEL ── */}
        <main style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>

          {/* Header */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 8 }}>
              <h1
                style={{
                  fontSize: 15,
                  fontWeight: 700,
                  color: '#e6edf3',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  fontFamily: 'JetBrains Mono, monospace',
                  margin: 0,
                }}
              >
                GameDNA Database
              </h1>
              <span
                style={{
                  fontSize: 11,
                  color: '#484f58',
                  fontFamily: 'JetBrains Mono, monospace',
                }}
              >
                {sorted.length.toLocaleString()} entries
              </span>
            </div>

            {/* Sort tabs */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 10, color: '#484f58', marginRight: 4 }}>Sort by:</span>
              {[
                { key: 'relevancy', label: 'Relevancy' },
                { key: 'release', label: 'Release Date' },
                { key: 'dna', label: 'DNA Match' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  className={`sort-tab ${sortTab === key ? 'active' : ''}`}
                  onClick={() => setSortTab(key)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Column headers */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 120px',
              padding: '4px 12px',
              marginBottom: 6,
              borderBottom: '1px solid #21262d',
            }}
          >
            <span style={{ fontSize: 10, color: '#484f58', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Game
            </span>
            <span style={{ fontSize: 10, color: '#484f58', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em', textAlign: 'center' }}>
              DNA Profile
            </span>
          </div>

          {/* Game list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sorted.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#484f58', fontSize: 13 }}>
                No games match your search.
              </div>
            ) : (
              sorted.map(game => <GameCard key={game.id} game={game} />)
            )}
          </div>

          {/* Stats bar */}
          <div
            style={{
              marginTop: 20,
              padding: '10px 14px',
              background: '#161b22',
              border: '1px solid #21262d',
              borderRadius: 6,
              display: 'flex',
              gap: 24,
            }}
          >
            {[
              { label: 'Total Games', value: '8,412' },
              { label: 'Avg DNA Score', value: '7.4' },
              { label: 'Last Updated', value: 'Jul 24, 2026' },
              { label: 'Contributors', value: '1,247' },
            ].map(({ label, value }) => (
              <div key={label}>
                <div style={{ fontSize: 9, color: '#484f58', fontFamily: 'JetBrains Mono, monospace', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {label}
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#58a6ff', fontFamily: 'JetBrains Mono, monospace' }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </main>
      </div>

      {/* ── FOOTER ── */}
      <footer
        style={{
          borderTop: '1px solid #21262d',
          background: '#161b22',
          padding: '10px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#484f58', letterSpacing: '-0.01em' }}>
            Game<span style={{ color: '#30363d' }}>DNA</span>
          </span>
          <span style={{ color: '#30363d', fontSize: 11 }}>·</span>
          {['About', 'API', 'Contribute', 'Privacy', 'Terms'].map(link => (
            <a
              key={link}
              href="#"
              style={{
                fontSize: 11,
                color: '#484f58',
                textDecoration: 'none',
                padding: '0 6px',
                transition: 'color 0.15s',
              }}
              onMouseEnter={e => ((e.target as HTMLAnchorElement).style.color = '#8b949e')}
              onMouseLeave={e => ((e.target as HTMLAnchorElement).style.color = '#484f58')}
            >
              {link}
            </a>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* X/Twitter */}
          <a href="#" style={{ color: '#484f58', transition: 'color 0.15s' }}
            onMouseEnter={e => ((e.target as HTMLAnchorElement).style.color = '#8b949e')}
            onMouseLeave={e => ((e.target as HTMLAnchorElement).style.color = '#484f58')}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>
          </a>
          {/* Reddit */}
          <a href="#" style={{ color: '#484f58', transition: 'color 0.15s' }}
            onMouseEnter={e => ((e.target as HTMLAnchorElement).style.color = '#8b949e')}
            onMouseLeave={e => ((e.target as HTMLAnchorElement).style.color = '#484f58')}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
            </svg>
          </a>
          {/* GitHub */}
          <a href="#" style={{ color: '#484f58', transition: 'color 0.15s' }}
            onMouseEnter={e => ((e.target as HTMLAnchorElement).style.color = '#8b949e')}
            onMouseLeave={e => ((e.target as HTMLAnchorElement).style.color = '#484f58')}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/>
            </svg>
          </a>
          <span style={{ fontSize: 10, color: '#30363d', fontFamily: 'JetBrains Mono, monospace', marginLeft: 8 }}>
            v2.4.1
          </span>
        </div>
      </footer>
    </div>
  )
}

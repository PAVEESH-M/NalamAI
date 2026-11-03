import { useState, useEffect, useRef, useCallback } from 'react'
import { sendChat, uploadPrescription, getFacilities, getEmergencyInfo, getHealth } from './api'

// ── Translations ───────────────────────────────────────────────────────────────
const T = {
  en: {
    subtitle: 'Tamil & English Health Assistant',
    chat: 'Chat',
    prescription: 'Prescription',
    facilities: 'Facilities',
    preventive: 'Preventive Health',
    placeholder: 'Ask a health question in English or Tamil...',
    send: 'Send',
    uploading: 'Reading...',
    upload_title: 'Upload a Prescription Photo',
    upload_hint: 'Drag & drop or click to upload a JPEG/PNG image',
    upload_formats: 'Supported: JPEG, PNG, WebP (max 10MB)',
    ocr_reading: 'Reading your prescription...',
    raw_text: 'Extracted Text',
    medicines_found: 'Medicines Found',
    explanation: 'Plain-Language Explanation',
    warnings: 'Important Warnings',
    pharmacist_note: 'Note',
    facilities_title: 'Healthcare Facilities in Tamil Nadu',
    hours: 'Hours',
    cost: 'Cost',
    how_to_find: 'How to find',
    emergency_title: '🚨 Emergency',
    ambulance: 'Ambulance',
    health_helpline: 'Health Helpline (free)',
    national: 'National Helpline',
    poison: 'Poison Control',
    mental: 'Mental Health',
    quick_prompts: [
      'What does my BP medicine do?',
      'How to prevent diabetes?',
      'My child has fever, what should I do?',
      'Where can I get free medicines?',
      'What are signs of a stroke?',
    ],
    welcome: "👋 Hello! I'm **NALAM AI**, your health information assistant.\n\nI can help you with:\n- Understanding your medicines (always verify with your pharmacist)\n- Preventive health tips\n- Finding healthcare facilities\n- Health questions in Tamil or English\n\nFor emergencies, call **108** immediately.",
    mock_badge: 'DEMO MODE',
  },
  ta: {
    subtitle: 'தமிழ் & ஆங்கில சுகாதார உதவியாளர்',
    chat: 'அரட்டை',
    prescription: 'மருந்து சீட்டு',
    facilities: 'வசதிகள்',
    preventive: 'தடுப்பு சுகாதாரம்',
    placeholder: 'ஆங்கிலம் அல்லது தமிழில் கேள்வி கேளுங்கள்...',
    send: 'அனுப்பு',
    uploading: 'படிக்கிறது...',
    upload_title: 'மருந்து சீட்டு படம் பதிவேற்றவும்',
    upload_hint: 'JPEG/PNG படத்தை இழுத்து விடுங்கள் அல்லது கிளிக் செய்யுங்கள்',
    upload_formats: 'ஆதரிக்கப்படுபவை: JPEG, PNG, WebP (அதிகபட்சம் 10MB)',
    ocr_reading: 'மருந்து சீட்டு படிக்கப்படுகிறது...',
    raw_text: 'எடுக்கப்பட்ட உரை',
    medicines_found: 'கண்டுபிடிக்கப்பட்ட மருந்துகள்',
    explanation: 'எளிய மொழியில் விளக்கம்',
    warnings: 'முக்கியமான எச்சரிக்கைகள்',
    pharmacist_note: 'குறிப்பு',
    facilities_title: 'தமிழ்நாட்டில் சுகாதார வசதிகள்',
    hours: 'நேரம்',
    cost: 'கட்டணம்',
    how_to_find: 'எப்படி கண்டுபிடிப்பது',
    emergency_title: '🚨 அவசரநிலை',
    ambulance: 'ஆம்புலன்ஸ்',
    health_helpline: 'சுகாதார உதவி (இலவசம்)',
    national: 'தேசிய உதவி',
    poison: 'விஷம் கட்டுப்பாடு',
    mental: 'மனநல உதவி',
    quick_prompts: [
      'என் BP மருந்து என்ன செய்கிறது?',
      'நீரிழிவை தடுப்பது எப்படி?',
      'என் குழந்தைக்கு காய்ச்சல், என்ன செய்வது?',
      'இலவச மருந்துகள் எங்கே கிடைக்கும்?',
      'பக்கவாதத்தின் அறிகுறிகள் என்ன?',
    ],
    welcome: "👋 வணக்கம்! நான் **NALAM AI**, உங்கள் சுகாதார தகவல் உதவியாளர்.\n\nநான் உதவுவது:\n- உங்கள் மருந்துகளை புரிந்துகொள்ள (மருந்தாளரிடம் சரிபார்க்கவும்)\n- தடுப்பு சுகாதார குறிப்புகள்\n- சுகாதார வசதிகள் கண்டுபிடிக்க\n- தமிழ் அல்லது ஆங்கிலத்தில் கேள்விகள்\n\nஅவசரநிலைக்கு உடனே **108** அழைக்கவும்.",
    mock_badge: 'டெமோ முறை',
  },
}

const PREVENTIVE_TIPS = {
  en: [
    { icon: '💊', title: 'Medicines', tip: 'Always take prescribed medicines at the same time each day. Never stop without asking your doctor.' },
    { icon: '🩺', title: 'Blood Pressure', tip: 'Check your BP at least once a year. Normal is below 120/80 mmHg. Reduce salt and exercise regularly.' },
    { icon: '🍎', title: 'Diabetes Prevention', tip: 'Eat more vegetables and less sugar. Exercise 30 minutes most days. Get fasting blood sugar checked annually after 30.' },
    { icon: '💉', title: 'Vaccinations', tip: 'Keep your children\'s immunisation schedule up to date. Adults should update tetanus boosters.' },
    { icon: '🧠', title: 'Mental Health', tip: 'Mental health matters. Call iCall 9152987821 for free counselling. There is no shame in seeking help.' },
    { icon: '👶', title: 'Child Health', tip: 'For children under 5: fever above 38.5°C for more than 2 days needs a doctor. Never give aspirin to children.' },
    { icon: '🤱', title: 'Maternal Health', tip: 'Pregnant? Attend at least 4 antenatal check-ups. Severe headache or face swelling needs immediate medical attention.' },
    { icon: '👁️', title: 'Eye Health', tip: 'Get an eye check every 2 years. If you have diabetes, check annually. Sudden vision loss needs urgent care.' },
  ],
  ta: [
    { icon: '💊', title: 'மருந்துகள்', tip: 'பரிந்துரைக்கப்பட்ட மருந்துகளை ஒவ்வொரு நாளும் ஒரே நேரத்தில் எடுங்கள். மருத்துவரிடம் கேட்காமல் நிறுத்தாதீர்கள்.' },
    { icon: '🩺', title: 'இரத்த அழுத்தம்', tip: 'ஆண்டுக்கு ஒருமுறை BP சரிபார்க்கவும். இயல்பு 120/80 mmHg-க்கு கீழ். உப்பை குறையுங்கள்.' },
    { icon: '🍎', title: 'நீரிழிவு தடுப்பு', tip: 'காய்கறிகள் அதிகம், சர்க்கரை குறைவாக சாப்பிடுங்கள். 30 வயதுக்கு பிறகு ஆண்டுதோறும் சர்க்கரை சோதிக்கவும்.' },
    { icon: '💉', title: 'தடுப்பூசிகள்', tip: 'குழந்தைகளின் தடுப்பூசி அட்டவணையை பின்பற்றுங்கள். பெரியவர்கள் தனுவாத தடுப்பூசி புதுப்பிக்கவும்.' },
    { icon: '🧠', title: 'மனநலம்', tip: 'மனநலம் முக்கியம். iCall 9152987821 இலவச ஆலோசனைக்கு. உதவி கேட்பதில் வெட்கமில்லை.' },
    { icon: '👶', title: 'குழந்தை சுகாதாரம்', tip: '5 வயதுக்கு கீழ்: 38.5°C-க்கு மேல் 2 நாளுக்கும் மேல் காய்ச்சல் இருந்தால் மருத்துவரை காணுங்கள்.' },
    { icon: '🤱', title: 'தாய் நலம்', tip: 'கர்ப்பமா? குறைந்தது 4 முறை கர்ப்பகால பரிசோதனை. தீவிர தலைவலி அல்லது முகம் வீக்கம் உடனே மருத்துவரை காணுங்கள்.' },
    { icon: '👁️', title: 'கண் சுகாதாரம்', tip: '2 ஆண்டுக்கு ஒருமுறை கண் பரிசோதனை. நீரிழிவு இருந்தால் ஆண்டுதோறும். திடீர் பார்வை இழப்பு உடனடி கவனம் தேவை.' },
  ],
}

// ── Sub-components ──────────────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="message assistant">
      <div className="msg-avatar">🏥</div>
      <div className="msg-bubble">
        <div className="typing-indicator">
          <div className="dot" /><div className="dot" /><div className="dot" />
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ msg }) {
  const isEmergency = msg.meta?.path?.includes('emergency')
  const isClinical = msg.meta?.path?.includes('clinical')
  const bubbleCls = `message ${msg.role}${isEmergency || isClinical ? ' emergency' : ''}`

  if (msg.role === 'user') {
    return (
      <div className={bubbleCls}>
        <div className="msg-avatar">YOU</div>
        <div className="msg-bubble">{msg.text}</div>
      </div>
    )
  }

  return (
    <div className={bubbleCls}>
      <div className="msg-avatar">🏥</div>
      <div className="msg-bubble">
        <div style={{ whiteSpace: 'pre-line' }}>{msg.answer}</div>
        {msg.steps?.length > 0 && (
          <div className="msg-steps">
            <ul>{msg.steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </div>
        )}
        {msg.safety_note && <div className="msg-safety">{msg.safety_note}</div>}
        {msg.escalation && (
          <div className="msg-escalation">📋 {msg.escalation}</div>
        )}
        {msg.citations?.length > 0 && (
          <div className="msg-citations">
            {msg.citations.map(c => <span key={c} className="citation-tag">{c}</span>)}
          </div>
        )}
        <div className="msg-path">
          {msg.meta?.path} {msg.meta?.latency_ms ? `· ${msg.meta.latency_ms}ms` : ''}
        </div>
      </div>
    </div>
  )
}

function ChatTab({ lang }) {
  const t = T[lang]
  const [messages, setMessages] = useState([
    { role: 'assistant', answer: t.welcome, steps: [], escalation: '', citations: [], meta: { path: 'welcome' } },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Reset welcome when language changes
  useEffect(() => {
    setMessages([
      { role: 'assistant', answer: T[lang].welcome, steps: [], escalation: '', citations: [], meta: { path: 'welcome' } },
    ])
  }, [lang])

  const send = useCallback(async (text) => {
    if (!text?.trim() || loading) return
    setError(null)
    const userMsg = { role: 'user', text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    try {
      const res = await sendChat(text, lang)
      setMessages(prev => [...prev, { role: 'assistant', ...res }])
    } catch (e) {
      const errMsg = e.response?.data?.detail || e.message || 'Network error'
      setError(errMsg)
      setMessages(prev => [...prev, {
        role: 'assistant',
        answer: `Sorry, I couldn't process that: ${errMsg}`,
        steps: [], escalation: '', citations: [], meta: { path: 'error' },
      }])
    } finally {
      setLoading(false)
    }
  }, [loading, lang])

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  return (
    <div>
      <div className="quick-prompts">
        {t.quick_prompts.map((p, i) => (
          <button key={i} className="quick-prompt-btn" onClick={() => send(p)}>{p}</button>
        ))}
      </div>
      <div className="card">
        <div className="chat-container">
          <div className="messages">
            {messages.map((m, i) => <MessageBubble key={i} msg={m} />)}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
          {error && <div className="error-msg">⚠️ {error}</div>}
          <div className="chat-input-area">
            <textarea
              ref={textareaRef}
              className={`chat-textarea${lang === 'ta' ? ' tamil' : ''}`}
              rows={2}
              placeholder={t.placeholder}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={onKey}
            />
            <button className="send-btn" onClick={() => send(input)} disabled={loading || !input.trim()}>
              {loading ? '...' : t.send}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function PrescriptionTab({ lang }) {
  const t = T[lang]
  const [dragOver, setDragOver] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [showRaw, setShowRaw] = useState(false)
  const inputRef = useRef(null)

  const upload = async (file) => {
    if (!file) return
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const res = await uploadPrescription(file)
      setResult(res)
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) upload(file)
  }

  return (
    <div>
      <div className="card">
        <div className="card-title">📋 {t.upload_title}</div>
        <div
          className={`upload-area${dragOver ? ' drag-over' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
        >
          <input ref={inputRef} type="file" accept="image/*" onChange={e => upload(e.target.files[0])} />
          <div className="upload-icon">{loading ? <div className="spinner" /> : '📷'}</div>
          <div className="upload-text">{loading ? t.ocr_reading : t.upload_hint}</div>
          <div className="upload-hint">{t.upload_formats}</div>
        </div>
        {error && <div className="error-msg">⚠️ {error}</div>}
      </div>

      {result && (
        <div className="card rx-result">
          {result.warnings.map((w, i) => (
            <div key={i} className="rx-warning">{w}</div>
          ))}

          {result.medicines?.length > 0 && (
            <>
              <div className="rx-section-title">{t.medicines_found} ({result.medicines.length})</div>
              {result.medicines.map((m, i) => (
                <div key={i} className="medicine-item">
                  <div className="medicine-name">{m.name || m}</div>
                  {(m.dose || m.frequency || m.duration) && (
                    <div className="medicine-detail">
                      {[m.dose, m.frequency, m.duration].filter(Boolean).join(' · ')}
                    </div>
                  )}
                </div>
              ))}
            </>
          )}

          <div className="rx-section-title">{t.explanation}</div>
          <div style={{ fontSize: '0.9rem', lineHeight: 1.7, whiteSpace: 'pre-line' }}>
            {result.explanation}
          </div>

          <div className="pharmacist-note">✅ {result.pharmacist_note}</div>

          <div style={{ marginTop: 12 }}>
            <button
              className="quick-prompt-btn"
              onClick={() => setShowRaw(!showRaw)}
              style={{ fontSize: '0.78rem' }}
            >
              {showRaw ? 'Hide' : 'Show'} {t.raw_text}
            </button>
          </div>
          {showRaw && (
            <>
              <div className="rx-section-title">{t.raw_text} ({result.ocr_method})</div>
              <div className="raw-text">{result.raw_text}</div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function FacilitiesTab({ lang }) {
  const t = T[lang]
  const [facilities, setFacilities] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getFacilities()
      .then(setFacilities)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="card" style={{ textAlign: 'center', padding: 40 }}><div className="spinner" /></div>
  if (error) return <div className="error-msg">⚠️ {error}</div>

  return (
    <div className="card">
      <div className="card-title">🏥 {t.facilities_title}</div>
      {facilities?.map((f, i) => (
        <div key={i} className="facility-item">
          <div className="facility-name">{f.name}</div>
          <div className="facility-type">{f.type?.replace('_', ' ')}</div>
          <div className="facility-detail">🩺 {f.services}</div>
          <div className="facility-detail">🕐 {t.hours}: {f.hours}</div>
          <div className="facility-detail">💰 {t.cost}: <strong>{f.cost}</strong></div>
          <div className="facility-detail">📍 {t.how_to_find}: {f.how_to_find}</div>
        </div>
      ))}
    </div>
  )
}

function PreventiveTab({ lang }) {
  const tips = PREVENTIVE_TIPS[lang] || PREVENTIVE_TIPS.en
  return (
    <div>
      {tips.map((tip, i) => (
        <div key={i} className="card" style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
          <div style={{ fontSize: '1.8rem', lineHeight: 1 }}>{tip.icon}</div>
          <div>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{tip.title}</div>
            <div style={{ fontSize: '0.88rem', color: 'var(--neutral-600)', lineHeight: 1.65 }}>{tip.tip}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function Sidebar({ lang }) {
  const t = T[lang]
  const [info, setInfo] = useState(null)

  useEffect(() => {
    getEmergencyInfo(lang)
      .then(setInfo)
      .catch(() => {})
  }, [lang])

  return (
    <aside className="sidebar">
      <div className="emergency-card">
        <div className="emergency-title">{t.emergency_title}</div>
        <span className="emergency-number">108</span>
        <div className="emergency-desc">{lang === 'ta' ? 'இந்தியா – ஆம்புலன்ஸ்' : 'India – Ambulance'}</div>
      </div>
      <div className="card">
        <div className="card-title">📞 {lang === 'ta' ? 'உதவி எண்கள்' : 'Helplines'}</div>
        {[
          [t.health_helpline, '104'],
          [t.national, '1800-180-1104'],
          [t.poison, '1800-116-117'],
          [t.mental, '9152987821'],
        ].map(([label, num]) => (
          <div key={num} className="helpline-item">
            <span style={{ fontSize: '0.82rem', color: 'var(--neutral-600)' }}>{label}</span>
            <span className="helpline-number">{num}</span>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="card-title">⚕️ {lang === 'ta' ? 'NALAM AI பற்றி' : 'About NALAM AI'}</div>
        <p style={{ fontSize: '0.82rem', color: 'var(--neutral-600)', lineHeight: 1.65 }}>
          {lang === 'ta'
            ? 'NALAM AI தமிழ்நாட்டில் உள்ள சேவை இல்லாத சமூகங்களுக்கு இலவச சுகாதார தகவல் வழங்குகிறது. நோய் கண்டறிதல் அல்ல, தகவல் மட்டுமே.'
            : 'NALAM AI provides free health information to underserved communities in Tamil Nadu. For information only — not a substitute for medical care.'}
        </p>
      </div>
    </aside>
  )
}

// ── Main App ───────────────────────────────────────────────────────────────────

export default function App() {
  const [lang, setLang] = useState('en')
  const [tab, setTab] = useState('chat')
  const [isMock, setIsMock] = useState(null)
  const t = T[lang]

  useEffect(() => {
    getHealth().then(h => setIsMock(h.mock)).catch(() => {})
  }, [])

  const tabs = [
    { id: 'chat', label: t.chat },
    { id: 'prescription', label: t.prescription },
    { id: 'facilities', label: t.facilities },
    { id: 'preventive', label: t.preventive },
  ]

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span style={{ fontSize: '1.6rem' }}>🏥</span>
            <div>
              <div className="logo-text">NALAM AI · நலம் AI</div>
              <div className="logo-sub">{t.subtitle}</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {isMock && <span className="badge-mock">{t.mock_badge}</span>}
            <div className="lang-toggle">
              <button className={`lang-btn${lang === 'en' ? ' active' : ''}`} onClick={() => setLang('en')}>EN</button>
              <button className={`lang-btn${lang === 'ta' ? ' active' : ''}`} onClick={() => setLang('ta')}>த</button>
            </div>
          </div>
        </div>
      </header>

      <div className="emergency-banner">
        🚨 {lang === 'ta' ? 'அவசரநிலைக்கு உடனே அழைக்கவும்:' : 'Medical Emergency?'}{' '}
        <strong><a href="tel:108">108</a></strong>
        {' '}·{' '}
        {lang === 'ta' ? 'சுகாதார உதவி:' : 'Health Helpline:'}{' '}
        <strong><a href="tel:104">104</a></strong>
      </div>

      <main className="main">
        <div>
          <nav className="nav-tabs">
            {tabs.map(tb => (
              <button
                key={tb.id}
                className={`nav-tab${tab === tb.id ? ' active' : ''}`}
                onClick={() => setTab(tb.id)}
              >
                {tb.label}
              </button>
            ))}
          </nav>

          {tab === 'chat'         && <ChatTab lang={lang} />}
          {tab === 'prescription' && <PrescriptionTab lang={lang} />}
          {tab === 'facilities'   && <FacilitiesTab lang={lang} />}
          {tab === 'preventive'   && <PreventiveTab lang={lang} />}
        </div>

        <Sidebar lang={lang} />
      </main>

      <footer className="footer">
        NALAM AI is for information only. Not a substitute for medical advice. Always consult a qualified healthcare professional. · நலம் AI — தகவல் மட்டுமே.
      </footer>
    </div>
  )
}

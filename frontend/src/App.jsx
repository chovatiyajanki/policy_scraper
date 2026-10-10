import { useState, useEffect, useCallback } from 'react'
import {
  Car,
  Search,
  Calendar,
  ShieldCheck,
  ChevronRight,
  RefreshCw,
  Trash2,
  Download,
  AlertCircle,
  X,
  FileText,
  User,
  MapPin,
  Gauge,
  Fuel,
  ExternalLink,
  LogOut,
  Clock,
  Layers,
  ChevronDown,
  Copy,
  Check,
  Zap
} from 'lucide-react'
import './App.css'
import AuthView from './AuthView'

export default function App() {
  const [authToken, setAuthToken] = useState(() => localStorage.getItem('auth_token'))
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('auth_user')
      return saved ? JSON.parse(saved) : null
    } catch {
      return null
    }
  })

  const [carNumber, setCarNumber] = useState('')
  const [forceRefresh, setForceRefresh] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [currentPolicy, setCurrentPolicy] = useState(null)
  const [history, setHistory] = useState([])
  const [historySearch, setHistorySearch] = useState('')
  const [editingExpiry, setEditingExpiry] = useState(false)
  const [tempExpiry, setTempExpiry] = useState('')
  const [showRawData, setShowRawData] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleLogout = useCallback(() => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    setAuthToken(null)
    setCurrentUser(null)
    setCurrentPolicy(null)
    setHistory([])
  }, [])

  const authFetch = useCallback(async (url, options = {}) => {
    const headers = {
      ...(options.headers || {})
    }
    const token = localStorage.getItem('auth_token') || authToken
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const res = await fetch(url, { ...options, headers })
    if (res.status === 401) {
      handleLogout()
      throw new Error('Session expired. Please sign in again.')
    }
    return res
  }, [authToken, handleLogout])

  const fetchHistory = useCallback(async () => {
    try {
      const res = await authFetch('/api/policies')
      if (res.ok) {
        const data = await res.json()
        setHistory(data.items || [])
      }
    } catch (err) {
      console.error('Error fetching history:', err)
    }
  }, [authFetch])

  const handleUpdateField = async (fields) => {
    if (!currentPolicy) return
    try {
      const res = await authFetch(`/api/policies/${currentPolicy.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fields)
      })
      if (res.ok) {
        const updated = await res.json()
        setCurrentPolicy(updated)
        fetchHistory()
        setEditingExpiry(false)
      }
    } catch (err) {
      console.error('Failed to update policy:', err)
    }
  }

  useEffect(() => {
    if (authToken) {
      fetchHistory()
    }
  }, [authToken, fetchHistory])

  const handleSearch = async (overrideCarNo = null) => {
    const targetNo = overrideCarNo || carNumber
    if (!targetNo || targetNo.trim().length < 5) {
      setError('Please enter a valid vehicle registration number.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const res = await authFetch('/api/policies/scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          registration_number: targetNo.trim(),
          force_refresh: forceRefresh
        })
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Failed to retrieve vehicle details.')
      }

      const policyData = await res.json()
      setCurrentPolicy(policyData)
      fetchHistory()
    } catch (err) {
      setError(err.message || 'Error occurred while scraping policy details.')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id, e) => {
    if (e) e.stopPropagation()
    if (!window.confirm('Are you sure you want to delete this record?')) return

    try {
      const res = await authFetch(`/api/policies/${id}`, { method: 'DELETE' })
      if (res.ok) {
        if (currentPolicy?.id === id) {
          setCurrentPolicy(null)
        }
        fetchHistory()
      }
    } catch (err) {
      console.error('Failed to delete policy:', err)
    }
  }

  const handleCopyJSON = () => {
    if (!currentPolicy) return
    navigator.clipboard.writeText(JSON.stringify(currentPolicy, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const exportToCSV = () => {
    if (history.length === 0) return
    const headers = [
      'Registration Number',
      'Make',
      'Model',
      'Variant',
      'Engine CC',
      'Transmission',
      'Fuel Type',
      'Vehicle Type',
      'Vehicle Class',
      'Registration Date',
      'Manufacturing Month',
      'Vehicle Age',
      'Policy Expiry Date',
      'Policy Status',
      'Days Status',
      'Insurance Provider',
      'Policy Type',
      'RTO Authority',
      'Registered Owner'
    ]
    const rows = history.map(item => {
      const meta = item.raw_data?.pb_metadata || {}
      return [
        `"${item.registration_number || ''}"`,
        `"${item.vehicle_make || ''}"`,
        `"${item.vehicle_model || ''}"`,
        `"${item.variant || ''}"`,
        `"${item.engine_cc || ''}"`,
        `"${meta.transmission || ''}"`,
        `"${item.fuel_type || ''}"`,
        `"${item.vehicle_type || ''}"`,
        `"${meta.vehicle_class || ''}"`,
        `"${item.registration_date || ''}"`,
        `"${item.manufacturing_month || ''}"`,
        `"${meta.vehicle_age || ''}"`,
        `"${item.policy_expiry_date || ''}"`,
        `"${item.policy_status || ''}"`,
        `"${meta.days_status_text || ''}"`,
        `"${meta.insurance_provider || item.raw_data?.previous_insurer || ''}"`,
        `"${meta.policy_type || ''}"`,
        `"${item.rto_name || ''}"`,
        `"${item.owner_name || ''}"`
      ]
    })

    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `policybazaar_vehicle_policies_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const filteredHistory = history.filter(item => {
    const q = historySearch.toLowerCase()
    return (
      (item.registration_number && item.registration_number.toLowerCase().includes(q)) ||
      (item.vehicle_model && item.vehicle_model.toLowerCase().includes(q)) ||
      (item.owner_name && item.owner_name.toLowerCase().includes(q)) ||
      (item.rto_name && item.rto_name.toLowerCase().includes(q))
    )
  })

  if (!authToken) {
    return (
      <AuthView
        onAuthSuccess={(token, user) => {
          setAuthToken(token)
          setCurrentUser(user)
        }}
      />
    )
  }

  const pbMeta = currentPolicy?.raw_data?.pb_metadata || {}
  const pbRc = currentPolicy?.raw_data?.rc || {}

  return (
    <div className="app-container">
      {/* App Header */}
      <header className="app-header">
        <div className="brand-wrapper">
          <div className="brand-icon">
            <Car size={26} />
          </div>
          <div>
            <h1 className="brand-title">PolicyBazaar Scraper</h1>
            <p className="brand-subtitle">Direct, Zero-API-Key Vehicle & Insurance Policy Intelligence</p>
          </div>
        </div>
        <div className="header-actions">
          <div className="header-user-badge" title={currentUser?.email || 'Authenticated User'}>
            <User size={15} />
            <span className="user-email-text">{currentUser?.full_name || currentUser?.email || 'User'}</span>
          </div>

          <button
            type="button"
            className="btn-logout"
            onClick={handleLogout}
            title="Sign out of your account"
          >
            <LogOut size={15} />
            <span>Sign Out</span>
          </button>

          <a
            href="https://www.policybazaar.com/motor-insurance/car-insurance/"
            target="_blank"
            rel="noopener noreferrer"
            className="external-link-btn"
            title="Open Policybazaar Car Insurance in new tab"
          >
            <ExternalLink size={16} />
            <span>Open Policybazaar</span>
          </a>
        </div>
      </header>

      {/* Search Hero Card */}
      <section className="search-card">
        <div className="search-title-wrap">
          <h2 className="search-heading">Instant PolicyBazaar Vehicle & Insurance Lookup</h2>
          <p className="search-desc">
            Directly scrapes all available specifications, engine capacity, registration dates, RTO jurisdiction, and authentic IRDAI policy expiry dates from PolicyBazaar.
          </p>
        </div>

        <form
          className="search-form"
          onSubmit={(e) => {
            e.preventDefault()
            handleSearch()
          }}
        >
          <div className="input-box-wrapper">
            <span className="plate-badge">IND</span>
            <input
              type="text"
              className="car-number-input"
              placeholder="ENTER VEHICLE NUMBER"
              value={carNumber}
              onChange={(e) => setCarNumber(e.target.value.toUpperCase())}
              disabled={loading}
            />
          </div>

          <button type="submit" className="search-btn" disabled={loading}>
            {loading ? (
              <>
                <div className="spinner"></div>
                <span>Scraping Policybazaar...</span>
              </>
            ) : (
              <>
                <Search size={18} />
                <span>Scrape All Details</span>
              </>
            )}
          </button>
        </form>

        <div className="search-options-row">
          <span style={{ fontSize: '13px', color: '#64748b' }}>
            Example format: XX00XX0000 (e.g. GJ05JW9172, GJ05JW9175)
          </span>

          <label className="force-refresh-label">
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(e) => setForceRefresh(e.target.checked)}
            />
            <span>Bypass Cache (Force Live Policybazaar Scrape)</span>
          </label>
        </div>

        {error && (
          <div style={{ marginTop: '16px', color: '#b91c1c', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '14px', background: '#fee2e2', padding: '10px', borderRadius: '8px' }}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}
      </section>

      {/* Main Results View */}
      {currentPolicy && (
        <section className="results-container">
          {/* Card 1: Exact UI Replica matching reference screenshots */}
          <div className="replica-modal-card">
            {/* Header */}
            <div className="replica-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                {pbMeta.make_logo && (
                  <img
                    src={pbMeta.make_logo}
                    alt={currentPolicy.vehicle_make || 'Make'}
                    className="make-brand-logo"
                    onError={(e) => { e.target.style.display = 'none' }}
                  />
                )}
                <div>
                  <h3 className="replica-car-title">
                    {currentPolicy.vehicle_model || currentPolicy.maker_model || '-'}
                  </h3>
                  {currentPolicy.variant && currentPolicy.variant !== currentPolicy.vehicle_model && (
                    <div style={{ fontSize: '13px', color: '#1967d2', fontWeight: 600, marginTop: '2px' }}>
                      {currentPolicy.variant}
                    </div>
                  )}
                </div>
              </div>
              <div className="replica-header-actions">
                <button
                  className="replica-close-btn"
                  onClick={() => setCurrentPolicy(null)}
                  title="Close view"
                >
                  <X size={14} />
                </button>
              </div>
            </div>

            {/* Subtitle / Key Badges */}
            <div className="replica-subtitle" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
              <span className="info-chip chip-plate">{currentPolicy.registration_number}</span>
              {currentPolicy.registration_year && (
                <span className="info-chip">{currentPolicy.registration_year}</span>
              )}
              {currentPolicy.fuel_type && (
                <span className="info-chip chip-fuel">{currentPolicy.fuel_type}</span>
              )}
              {pbMeta.transmission && (
                <span className="info-chip chip-trans">{pbMeta.transmission}</span>
              )}
              {pbMeta.vehicle_class && (
                <span className="info-chip chip-class">{pbMeta.vehicle_class}</span>
              )}
              {pbMeta.vehicle_age && (
                <span className="info-chip chip-age" title="Vehicle Age from Registration Date">
                  <Clock size={12} style={{ display: 'inline', marginRight: '4px' }} />
                  {pbMeta.vehicle_age}
                </span>
              )}
            </div>

            {/* Vehicle Type Section */}
            <div className="replica-section-label">Vehicle type</div>
            <div className="vehicle-type-pills">
              <button
                type="button"
                className={`type-pill ${currentPolicy.vehicle_type === 'Private' ? 'active' : ''}`}
                onClick={() => handleUpdateField({ vehicle_type: 'Private' })}
                title="Set as Private vehicle"
              >
                Private
              </button>
              <button
                type="button"
                className={`type-pill ${currentPolicy.vehicle_type === 'Commercial' ? 'active' : ''}`}
                onClick={() => handleUpdateField({ vehicle_type: 'Commercial' })}
                title="Set as Commercial vehicle"
              >
                Commercial
              </button>
            </div>

            {/* Box 1: Registration Date with Floating Label & Calendar Icon */}
            <div className="floating-field-box">
              <span className="floating-label">Registration Date</span>
              <span className="floating-value">
                {currentPolicy.registration_date || '-'}
              </span>
              <Calendar size={18} className="floating-icon" />
            </div>

            {/* Box 2: Manufacturing month with Floating Label & Calendar Icon */}
            <div className="floating-field-box">
              <span className="floating-label">Manufacturing month</span>
              <span className="floating-value">
                {currentPolicy.manufacturing_month || '-'}
              </span>
              <Calendar size={18} className="floating-icon" />
            </div>

            {/* Policy Expiry Date Row */}
            <div className="policy-expiry-banner">
              <div className="expiry-left">
                <ShieldCheck size={20} color="#1967d2" />
                <div>
                  <span className="expiry-title">Policy Expiry Date</span>
                  {pbMeta.days_status_text && (
                    <div style={{ fontSize: '11px', color: currentPolicy.policy_status === 'Expired' ? '#b91c1c' : '#15803d', fontWeight: 600 }}>
                      {pbMeta.days_status_text}
                    </div>
                  )}
                </div>
              </div>
              <div className="expiry-right">
                {editingExpiry ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <input
                      type="text"
                      value={tempExpiry}
                      onChange={(e) => setTempExpiry(e.target.value)}
                      placeholder="DD-Mon-YYYY"
                      style={{
                        padding: '4px 8px',
                        fontSize: '13px',
                        border: '1.5px solid #1967d2',
                        borderRadius: '6px',
                        width: '120px'
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => handleUpdateField({ policy_expiry_date: tempExpiry })}
                      style={{
                        background: '#1967d2',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '4px',
                        padding: '4px 8px',
                        fontSize: '12px',
                        cursor: 'pointer'
                      }}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingExpiry(false)}
                      style={{
                        background: '#e2e8f0',
                        color: '#475569',
                        border: 'none',
                        borderRadius: '4px',
                        padding: '4px 6px',
                        fontSize: '12px',
                        cursor: 'pointer'
                      }}
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <>
                    <span
                      className="expiry-date-link"
                      onClick={() => {
                        setTempExpiry(currentPolicy.policy_expiry_date || '')
                        setEditingExpiry(true)
                      }}
                      title="Click to edit expiry date"
                      style={{ cursor: 'pointer' }}
                    >
                      {currentPolicy.policy_expiry_date || '-'}
                      <ChevronRight size={16} />
                    </span>
                    {currentPolicy.policy_status && (
                      <span className={`expiry-badge ${currentPolicy.policy_status === 'Expiring Soon' ? 'expiring-soon' : currentPolicy.policy_status === 'Expired' ? 'expired' : 'active'}`}>
                        {currentPolicy.policy_status}
                      </span>
                    )}
                  </>
                )}
              </div>
            </div>

            <button
              className="replica-action-btn"
              onClick={() => handleSearch(currentPolicy.registration_number)}
            >
              <RefreshCw size={16} />
              Re-Scrape Policybazaar
            </button>
          </div>

          {/* Card 2: Comprehensive Specifications & Stored Metadata */}
          <div className="details-panel">
            <div className="panel-header">
              <div>
                <h3 className="panel-title">
                  <FileText size={20} color="#1967d2" />
                  All Scraped Policybazaar Specifications
                </h3>
                <p style={{ fontSize: '12.5px', color: '#64748b', marginTop: '2px' }}>
                  Every detail scraped directly from Policybazaar's national VAHAN and quotes portal.
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  className="table-action-btn btn-view"
                  onClick={() => setShowRawData(!showRawData)}
                  title="Toggle raw Policybazaar JSON metadata"
                >
                  <Layers size={13} />
                  <span>{showRawData ? 'Hide All Data' : 'View All Data'}</span>
                  <ChevronDown size={12} style={{ transform: showRawData ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                </button>
              </div>
            </div>

            <div className="specs-grid">
              <div className="spec-item">
                <div className="spec-label">Car Variant</div>
                <div className="spec-val">{currentPolicy.variant || '-'}</div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Engine Capacity</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Gauge size={15} color="#64748b" />
                  {currentPolicy.engine_cc ? `${currentPolicy.engine_cc} CC` : '-'}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Transmission</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Zap size={15} color="#64748b" />
                  {pbMeta.transmission || 'Manual'}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Fuel Type</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Fuel size={15} color="#64748b" />
                  {currentPolicy.fuel_type || '-'}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Insurance Provider</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <ShieldCheck size={15} color="#1967d2" />
                  {pbMeta.insurance_provider || currentPolicy.raw_data?.previous_insurer || 'IRDAI Insured'}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Policy Type</div>
                <div className="spec-val">
                  {pbMeta.policy_type || 'Comprehensive (OD + TP)'}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">RTO Authority</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <MapPin size={15} color="#64748b" />
                  {currentPolicy.rto_name ? `${currentPolicy.rto_name} (${currentPolicy.rto_code || ''})` : (currentPolicy.rto_code || '-')}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Vehicle Class</div>
                <div className="spec-val">
                  {pbMeta.vehicle_class || 'LMV (Light Motor Vehicle)'}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Vehicle Age</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Clock size={15} color="#64748b" />
                  {pbMeta.vehicle_age || '-'}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Seating Capacity</div>
                <div className="spec-val">{currentPolicy.seating_capacity ? `${currentPolicy.seating_capacity} Seats` : '5 Seats'}</div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Plate Type</div>
                <div className="spec-val">
                  {pbMeta.is_bh_series ? 'Bharat Series (BH Plate)' : 'Standard State Plate'}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Registered Owner</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <User size={15} color="#64748b" />
                  {currentPolicy.owner_name || 'Protected by MoRTH'}
                </div>
              </div>

              <div className="spec-item" style={{ gridColumn: 'span 2' }}>
                <div className="spec-label">Full Maker Description</div>
                <div className="spec-val" style={{ fontSize: '13px', lineHeight: 1.4 }}>
                  {currentPolicy.maker_model || '-'}
                </div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Policybazaar Source</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#15803d', fontWeight: 600 }}>
                  <Check size={14} />
                  {pbMeta.vehicle_source?.toUpperCase() || 'VAHAN'} Verified
                </div>
              </div>

              {pbMeta.renewal_idv && (
                <div className="spec-item">
                  <div className="spec-label">Policybazaar Renewal IDV</div>
                  <div className="spec-val" style={{ color: '#0f766e', fontWeight: 700 }}>
                    ₹{Number(pbMeta.renewal_idv).toLocaleString('en-IN')}
                  </div>
                </div>
              )}

              {pbMeta.previous_policy_details?.finalPremium && (
                <div className="spec-item">
                  <div className="spec-label">Policybazaar Renewal Premium</div>
                  <div className="spec-val" style={{ color: '#15803d', fontWeight: 700 }}>
                    ₹{Number(pbMeta.previous_policy_details.finalPremium).toLocaleString('en-IN')}
                  </div>
                </div>
              )}
            </div>

            {/* Expandable PolicyBazaar Full Extracted Metadata Card */}
            {showRawData && (
              <div className="pb-meta-expanded-box">
                <div className="pb-meta-header">
                  <div>
                    <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#0f172a' }}>
                      Policybazaar Internal System Identifiers & Master Specs
                    </h4>
                    <p style={{ margin: '2px 0 0', fontSize: '12px', color: '#64748b' }}>
                      All internal IDs, catalogue codes, and VAHAN registry parameters retrieved from Policybazaar
                    </p>
                  </div>
                  <button
                    type="button"
                    className="copy-json-btn"
                    onClick={handleCopyJSON}
                  >
                    {copied ? <Check size={13} color="#15803d" /> : <Copy size={13} />}
                    <span>{copied ? 'Copied JSON!' : 'Copy Full JSON'}</span>
                  </button>
                </div>

                <div className="pb-id-pills-row">
                  <div className="id-pill">
                    <span className="id-label">PB Vehicle Code:</span>
                    <span className="id-val">{pbRc.vehicleCode || pbMeta.vehicle_code || '-'}</span>
                  </div>
                  <div className="id-pill">
                    <span className="id-label">Make ID:</span>
                    <span className="id-val">{pbRc.MakeId || pbMeta.make_id || '-'}</span>
                  </div>
                  <div className="id-pill">
                    <span className="id-label">Model ID:</span>
                    <span className="id-val">{pbRc.ModelId || pbMeta.model_id || '-'}</span>
                  </div>
                  <div className="id-pill">
                    <span className="id-label">Variant ID:</span>
                    <span className="id-val">{pbRc.VariantId || pbMeta.variant_id || '-'}</span>
                  </div>
                  <div className="id-pill">
                    <span className="id-label">PB RTO ID:</span>
                    <span className="id-val">{pbRc.rtoId || pbMeta.rto_id || '-'}</span>
                  </div>
                  <div className="id-pill">
                    <span className="id-label">Prev Insurer ID:</span>
                    <span className="id-val">{pbRc.previousInsurerId || pbMeta.previous_insurer_id || '-'}</span>
                  </div>
                  {pbMeta.enquiry_id && (
                    <div className="id-pill">
                      <span className="id-label">Enquiry ID:</span>
                      <span className="id-val" style={{ maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{pbMeta.enquiry_id}</span>
                    </div>
                  )}
                </div>

                <div className="raw-json-viewer">
                  <pre>{JSON.stringify(currentPolicy, null, 2)}</pre>
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
              <button
                className="table-action-btn btn-delete"
                onClick={(e) => handleDelete(currentPolicy.id, e)}
              >
                <Trash2 size={14} />
                Delete Record
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Database History Table */}
      <section className="history-section">
        <div className="history-header">
          <div className="history-title">
            <Car size={20} color="#1967d2" />
            <span>Policybazaar Scraped Policies Database ({history.length} records)</span>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <input
              type="text"
              placeholder="Filter by car number or model..."
              value={historySearch}
              onChange={(e) => setHistorySearch(e.target.value)}
              style={{
                padding: '8px 14px',
                border: '1px solid #cbd5e1',
                borderRadius: '8px',
                fontSize: '13px',
                width: '240px'
              }}
            />
            <button
              className="table-action-btn btn-view"
              onClick={exportToCSV}
              disabled={history.length === 0}
              title="Download Comprehensive CSV"
            >
              <Download size={14} />
              Export All Details CSV
            </button>
          </div>
        </div>

        {filteredHistory.length === 0 ? (
          <div className="empty-state">
            <Car size={36} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
            <p>No vehicle policy records found in the database.</p>
            <p style={{ fontSize: '13px', marginTop: '4px' }}>Enter a car number above to scrape and save all Policybazaar details.</p>
          </div>
        ) : (
          <div className="history-table-container">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Registration No</th>
                  <th>Vehicle Model & Variant</th>
                  <th>Engine / Fuel</th>
                  <th>Registration Date</th>
                  <th>Manufacturing Month</th>
                  <th>Policy Expiry Date</th>
                  <th>Insurance Provider</th>
                  <th>Status</th>
                  <th>RTO City</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredHistory.map((item) => {
                  const meta = item.raw_data?.pb_metadata || {}
                  return (
                    <tr
                      key={item.id}
                      style={{
                        cursor: 'pointer',
                        background: currentPolicy?.id === item.id ? '#eff6ff' : 'transparent'
                      }}
                      onClick={() => setCurrentPolicy(item)}
                    >
                      <td>
                        <span className="table-car-num">{item.registration_number}</span>
                      </td>
                      <td>
                        <div>
                          <strong>{item.vehicle_model || item.maker_model || '-'}</strong>
                          {item.variant && item.variant !== item.vehicle_model && (
                            <div style={{ fontSize: '12px', color: '#64748b' }}>{item.variant}</div>
                          )}
                        </div>
                      </td>
                      <td>
                        <span style={{ fontSize: '12.5px' }}>
                          {item.engine_cc ? `${item.engine_cc} CC` : '-'}
                          {item.fuel_type ? ` • ${item.fuel_type}` : ''}
                        </span>
                      </td>
                      <td>{item.registration_date || '-'}</td>
                      <td>{item.manufacturing_month || '-'}</td>
                      <td>
                        <strong style={{ color: '#1967d2' }}>{item.policy_expiry_date || '-'}</strong>
                        {meta.days_status_text && (
                          <div style={{ fontSize: '11px', color: item.policy_status === 'Expired' ? '#b91c1c' : '#15803d' }}>
                            {meta.days_status_text}
                          </div>
                        )}
                      </td>
                      <td>
                        <span style={{ fontSize: '12.5px' }}>
                          {meta.insurance_provider || item.raw_data?.previous_insurer || '-'}
                        </span>
                      </td>
                      <td>
                        {item.policy_status ? (
                          <span
                            className={`expiry-badge ${item.policy_status === 'Expiring Soon' ? 'expiring-soon' : item.policy_status === 'Expired' ? 'expired' : 'active'}`}
                          >
                            {item.policy_status}
                          </span>
                        ) : '-'}
                      </td>
                      <td>{item.rto_name || '-'}</td>
                      <td>
                        <button
                          className="table-action-btn btn-view"
                          onClick={(e) => {
                            e.stopPropagation()
                            setCurrentPolicy(item)
                          }}
                        >
                          View
                        </button>
                        <button
                          className="table-action-btn btn-delete"
                          onClick={(e) => handleDelete(item.id, e)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

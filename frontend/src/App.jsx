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
  LogOut
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

  // Load history on mount or when auth state updates
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

  const exportToCSV = () => {
    if (history.length === 0) return
    const headers = [
      'Registration Number',
      'Vehicle Model',
      'Make',
      'Registration Date',
      'Manufacturing Month',
      'Fuel Type',
      'Vehicle Type',
      'Policy Expiry Date',
      'Policy Status',
      'RTO',
      'Owner Name'
    ]
    const rows = history.map(item => [
      `"${item.registration_number || ''}"`,
      `"${item.vehicle_model || item.maker_model || ''}"`,
      `"${item.vehicle_make || ''}"`,
      `"${item.registration_date || ''}"`,
      `"${item.manufacturing_month || ''}"`,
      `"${item.fuel_type || ''}"`,
      `"${item.vehicle_type || ''}"`,
      `"${item.policy_expiry_date || ''}"`,
      `"${item.policy_status || ''}"`,
      `"${item.rto_name || ''}"`,
      `"${item.owner_name || ''}"`
    ])

    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `vehicle_policies_${new Date().toISOString().slice(0, 10)}.csv`)
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

  return (
    <div className="app-container">
      {/* App Header */}
      <header className="app-header">
        <div className="brand-wrapper">
          <div className="brand-icon">
            <Car size={26} />
          </div>
          <div>
            <h1 className="brand-title">AutoPolicy Scraper</h1>
            <p className="brand-subtitle">Automated Indian Vehicle & Insurance Policy Intelligence</p>
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
          <h2 className="search-heading">Instant Car Policy & Specs Lookup</h2>
          <p className="search-desc">
            Enter any Indian vehicle registration plate to extract model, manufacturing month, registration date, and policy expiry date.
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
                <span>Scraping...</span>
              </>
            ) : (
              <>
                <Search size={18} />
                <span>Search Policy</span>
              </>
            )}
          </button>
        </form>

        <div className="search-options-row">
          <span style={{ fontSize: '13px', color: '#64748b' }}>
            Example format: XX00XX0000
          </span>

          <label className="force-refresh-label">
            <input
              type="checkbox"
              checked={forceRefresh}
              onChange={(e) => setForceRefresh(e.target.checked)}
            />
            <span>Bypass Cache (Force Live Scrape)</span>
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
              <h3 className="replica-car-title">
                {currentPolicy.vehicle_model || currentPolicy.maker_model || '-'}
              </h3>
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

            {/* Subtitle */}
            <div className="replica-subtitle">
              {[
                currentPolicy.registration_number,
                currentPolicy.registration_year,
                currentPolicy.fuel_type
              ].filter(Boolean).join(' | ')}
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
                <span className="expiry-title">Policy Expiry Date</span>
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
              Re-Scrape Live Details
            </button>
          </div>

          {/* Card 2: Full Specifications & Stored Metadata */}
          <div className="details-panel">
            <div className="panel-header">
              <h3 className="panel-title">
                <FileText size={20} color="#1967d2" />
                Comprehensive Vehicle Specs
              </h3>
              <span style={{ fontSize: '13px', color: '#64748b' }}>
                Stored in PostgreSQL #{currentPolicy.id}
              </span>
            </div>

            <div className="specs-grid">
              <div className="spec-item">
                <div className="spec-label">Car Variant</div>
                <div className="spec-val">{currentPolicy.variant || '-'}</div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Registered Owner</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <User size={15} color="#64748b" />
                  {currentPolicy.owner_name || '-'}
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
                <div className="spec-label">Engine Capacity</div>
                <div className="spec-val" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Gauge size={15} color="#64748b" />
                  {currentPolicy.engine_cc ? `${currentPolicy.engine_cc} CC` : '-'}
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
                <div className="spec-label">Vehicle Color</div>
                <div className="spec-val">{currentPolicy.color || '-'}</div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Seating Capacity</div>
                <div className="spec-val">{currentPolicy.seating_capacity ? `${currentPolicy.seating_capacity} Seats` : '-'}</div>
              </div>

              <div className="spec-item">
                <div className="spec-label">Full Maker Description</div>
                <div className="spec-val" style={{ fontSize: '13px', lineHeight: 1.4 }}>
                  {currentPolicy.maker_model || '-'}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
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
            <span>Scraped Policies Database ({history.length} records)</span>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <input
              type="text"
              placeholder="Filter by car number or owner..."
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
              title="Download CSV"
            >
              <Download size={14} />
              Export CSV
            </button>
          </div>
        </div>

        {filteredHistory.length === 0 ? (
          <div className="empty-state">
            <Car size={36} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
            <p>No vehicle policy records found in the database.</p>
            <p style={{ fontSize: '13px', marginTop: '4px' }}>Enter a car number above to scrape and save details.</p>
          </div>
        ) : (
          <div className="history-table-container">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Registration No</th>
                  <th>Vehicle Model</th>
                  <th>Registration Date</th>
                  <th>Manufacturing Month</th>
                  <th>Fuel</th>
                  <th>Type</th>
                  <th>Policy Expiry Date</th>
                  <th>Status</th>
                  <th>RTO City</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredHistory.map((item) => (
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
                      <strong>{item.vehicle_model || item.maker_model || '-'}</strong>
                    </td>
                    <td>{item.registration_date || '-'}</td>
                    <td>{item.manufacturing_month || '-'}</td>
                    <td>{item.fuel_type || '-'}</td>
                    <td>{item.vehicle_type || '-'}</td>
                    <td>
                      <strong style={{ color: '#1967d2' }}>{item.policy_expiry_date || '-'}</strong>
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
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

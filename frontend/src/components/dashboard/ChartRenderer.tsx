import React, { useState, Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell
} from 'recharts'
import { ChevronDown, Eye, EyeOff } from 'lucide-react'
import type { ChartSpec } from '../../types/chat'
import { useThemeStore } from '../../store/themeStore'

const COLORS = ['#2563eb', '#16a34a', '#dc2626', '#d97706', '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b']

interface ChartRendererProps {
  spec: ChartSpec
}

// React Error Boundary to catch render-time chart crashes
interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

class ChartErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  public state: ErrorBoundaryState = {
    hasError: false
  }

  public static getDerivedStateFromError(_: Error): ErrorBoundaryState {
    return { hasError: true }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ChartRenderer crashed:', error, errorInfo)
  }

  public render() {
    if (this.state.hasError) {
      return null // Silent degradation: render nothing on crash
    }
    return this.props.children
  }
}

const ChartRendererInner: React.FC<ChartRendererProps> = ({ spec }) => {
  if (!spec || !spec.data || spec.data.length === 0) {
    return null
  }

  const { theme } = useThemeStore()
  const isDark = theme === 'dark'

  const [selectedType, setSelectedType] = useState<'bar' | 'line' | 'area' | 'pie'>(spec.chart_type)
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [isChartVisible, setIsChartVisible] = useState(true)

  // Derive available types
  const availableTypes: ('bar' | 'line' | 'area' | 'pie')[] =
    spec.y_keys.length > 1
      ? ['bar', 'line', 'area']
      : ['bar', 'line', 'area', 'pie']

  const handleToggleDropdown = () => {
    setIsDropdownOpen((prev) => !prev)
  }

  const handleSelectType = (type: 'bar' | 'line' | 'area' | 'pie') => {
    setSelectedType(type)
    setIsDropdownOpen(false)
  }

  // Theme values for Recharts SVG rendering
  const gridStroke = isDark ? '#334155' : '#f1f5f9' // slate-700 vs slate-100
  const tickColor = isDark ? '#94a3b8' : '#64748b'  // slate-400 vs slate-500
  const axisStroke = isDark ? '#475569' : '#cbd5e1' // slate-600 vs slate-300
  const tooltipBg = isDark ? '#1e293b' : '#ffffff'   // slate-800 vs white
  const tooltipBorder = isDark ? '#334155' : '#e2e8f0' // slate-700 vs slate-200
  const tooltipText = isDark ? '#f8fafc' : '#0f172a'   // slate-50 vs slate-900

  const renderChart = () => {
    switch (selectedType) {
      case 'line':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={spec.data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridStroke} />
              <XAxis dataKey={spec.x_key} tick={{ fontSize: 12, fill: tickColor }} stroke={axisStroke} />
              <YAxis tick={{ fontSize: 12, fill: tickColor }} stroke={axisStroke} />
              <Tooltip
                contentStyle={{
                  backgroundColor: tooltipBg,
                  borderColor: tooltipBorder,
                  color: tooltipText,
                  borderRadius: '8px',
                  fontSize: '12px'
                }}
              />
              {spec.y_keys.length > 1 && (
                <Legend
                  formatter={(value) => <span className="text-slate-600 dark:text-slate-400">{value}</span>}
                  wrapperStyle={{ fontSize: '12px', marginTop: '10px' }}
                />
              )}
              {spec.y_keys.map((key, index) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={COLORS[index % COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )

      case 'area':
        return (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={spec.data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridStroke} />
              <XAxis dataKey={spec.x_key} tick={{ fontSize: 12, fill: tickColor }} stroke={axisStroke} />
              <YAxis tick={{ fontSize: 12, fill: tickColor }} stroke={axisStroke} />
              <Tooltip
                contentStyle={{
                  backgroundColor: tooltipBg,
                  borderColor: tooltipBorder,
                  color: tooltipText,
                  borderRadius: '8px',
                  fontSize: '12px'
                }}
              />
              {spec.y_keys.length > 1 && (
                <Legend
                  formatter={(value) => <span className="text-slate-600 dark:text-slate-400">{value}</span>}
                  wrapperStyle={{ fontSize: '12px', marginTop: '10px' }}
                />
              )}
              {spec.y_keys.map((key, index) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  fill={COLORS[index % COLORS.length]}
                  stroke={COLORS[index % COLORS.length]}
                  fillOpacity={0.15}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        )

      case 'pie':
        // Map spec.data so each entry uses spec.x_key as name and spec.y_keys[0] as value
        const mappedPieData = spec.data.map((item) => ({
          name: String(item[spec.x_key]),
          value: Number(item[spec.y_keys[0]] || 0)
        }))

        return (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={mappedPieData}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label={({ name, percent, cx, cy, midAngle, outerRadius }) => {
                  const RADIAN = Math.PI / 180
                  const radius = outerRadius + 20
                  const x = cx + radius * Math.cos(-midAngle * RADIAN)
                  const y = cy + radius * Math.sin(-midAngle * RADIAN)
                  return (
                    <text
                      x={x}
                      y={y}
                      fill={tickColor}
                      textAnchor={x > cx ? 'start' : 'end'}
                      dominantBaseline="central"
                      fontSize={10}
                      className="font-medium"
                    >
                      {`${name}: ${(percent * 100).toFixed(0)}%`}
                    </text>
                  )
                }}
              >
                {mappedPieData.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: tooltipBg,
                  borderColor: tooltipBorder,
                  color: tooltipText,
                  borderRadius: '8px',
                  fontSize: '12px'
                }}
              />
              <Legend
                formatter={(value) => <span className="text-slate-600 dark:text-slate-400">{value}</span>}
                wrapperStyle={{ fontSize: '12px' }}
              />
            </PieChart>
          </ResponsiveContainer>
        )

      case 'bar':
      default:
        return (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={spec.data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridStroke} />
              <XAxis dataKey={spec.x_key} tick={{ fontSize: 12, fill: tickColor }} stroke={axisStroke} />
              <YAxis tick={{ fontSize: 12, fill: tickColor }} stroke={axisStroke} />
              <Tooltip
                contentStyle={{
                  backgroundColor: tooltipBg,
                  borderColor: tooltipBorder,
                  color: tooltipText,
                  borderRadius: '8px',
                  fontSize: '12px'
                }}
              />
              {spec.y_keys.length > 1 && (
                <Legend
                  formatter={(value) => <span className="text-slate-600 dark:text-slate-400">{value}</span>}
                  wrapperStyle={{ fontSize: '12px', marginTop: '10px' }}
                />
              )}
              {spec.y_keys.map((key, index) => (
                <Bar
                  key={key}
                  dataKey={key}
                  fill={COLORS[index % COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )
    }
  }

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 mt-3 shadow-sm select-none">
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2 mb-4">
        <h4 className="text-sm font-semibold text-slate-700 dark:text-slate-200 truncate pr-4">{spec.title}</h4>
        
        <div className="flex items-center gap-2">
          {/* Toggle for visual representation */}
          <button
            type="button"
            onClick={() => setIsChartVisible(!isChartVisible)}
            className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 transition-colors px-2 py-1.5 rounded border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
          >
            {isChartVisible ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>{isChartVisible ? 'Hide Chart' : 'Show Chart'}</span>
          </button>

          {/* Custom Select Dropdown with animated Chevron */}
          {isChartVisible && (
            <div className="relative">
              <button
                type="button"
                onClick={handleToggleDropdown}
                className="flex items-center gap-1.5 text-xs bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded px-2.5 py-1.5 text-slate-600 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer transition-all hover:bg-slate-100 dark:hover:bg-slate-700/50"
              >
                <span className="capitalize">{selectedType}</span>
                <ChevronDown
                  className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${
                    isDropdownOpen ? 'rotate-180' : ''
                  }`}
                />
              </button>

              {isDropdownOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setIsDropdownOpen(false)} />
                  <div className="absolute right-0 mt-1 w-24 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded shadow-lg z-20 py-1 overflow-hidden">
                    {availableTypes.map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => handleSelectType(t)}
                        className={`w-full text-left px-3 py-1.5 text-xs capitalize transition-colors ${
                          selectedType === t
                            ? 'bg-indigo-50 dark:bg-indigo-950/45 text-indigo-600 dark:text-indigo-400 font-medium'
                            : 'text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700/30'
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {isChartVisible && (
        <div className="w-full overflow-hidden transition-all duration-300">
          {renderChart()}
        </div>
      )}
    </div>
  )
}

export const ChartRenderer: React.FC<ChartRendererProps> = ({ spec }) => {
  return (
    <ChartErrorBoundary>
      <ChartRendererInner spec={spec} />
    </ChartErrorBoundary>
  )
}

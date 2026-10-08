export interface RoleLLM {
  provider: string
  model: string
  base_url: string | null
  reasoning_effort: string | null
}

export interface AgentLLMs {
  analysts: RoleLLM
  bull_researcher: RoleLLM
  bear_researcher: RoleLLM
  research_manager: RoleLLM
  trader: RoleLLM
  debators: RoleLLM
  portfolio_manager: RoleLLM
}

export interface DataVendors {
  core_stock_apis: string
  technical_indicators: string
  fundamental_data: string
  news_data: string
}

export interface Settings {
  llm_provider: string
  backend_url: string | null
  quick_think_llm: string
  deep_think_llm: string
  anthropic_effort: string | null
  google_thinking_level: string | null
  openai_reasoning_effort: string | null
  research_depth: number
  analysts: string[]
  output_language: string
  data_vendors: DataVendors
  agent_llms: AgentLLMs
}

export const PROVIDERS = [
  'openai',
  'anthropic',
  'google',
  'deepseek',
  'xai',
  'qwen',
  'glm',
  'ollama',
  'openrouter',
  'perplexity',
  'azure',
] as const

export const EFFORT_PROVIDERS = new Set(['openai', 'anthropic', 'google'])

export const DEFAULT_MODELS: Record<string, string> = {
  openai: 'gpt-4.1-mini',
  anthropic: 'claude-sonnet-4-6',
  google: 'gemini-2.5-flash',
  deepseek: 'deepseek-chat',
  xai: 'grok-3-mini',
  qwen: 'qwen-turbo',
  glm: 'glm-4-flash',
  ollama: 'llama3.2',
  openrouter: 'openai/gpt-4o-mini',
  perplexity: 'sonar',
  azure: 'gpt-4o',
}

export const ROLE_LABELS: Record<keyof AgentLLMs, string> = {
  analysts: 'Analysts',
  bull_researcher: 'Bull Researcher',
  bear_researcher: 'Bear Researcher',
  research_manager: 'Research Manager',
  trader: 'Trader',
  debators: 'Debators',
  portfolio_manager: 'Portfolio Manager',
}

export const ROLE_DESC: Record<keyof AgentLLMs, string> = {
  analysts: 'Market, social, news & fundamentals data collection',
  bull_researcher: 'Argues the bullish case for the position',
  bear_researcher: 'Argues the bearish case against the position',
  research_manager: 'Resolves the bull/bear debate (deep-think)',
  trader: 'Generates the trade recommendation',
  debators: 'Risk panel: aggressive / neutral / conservative',
  portfolio_manager: 'Final portfolio decision (deep-think)',
}

export const ANALYST_OPTIONS = [
  { value: 'market', label: 'Market' },
  { value: 'social', label: 'Social' },
  { value: 'news', label: 'News' },
  { value: 'fundamentals', label: 'Fundamentals' },
]

import axios from 'axios';
import type {
  Competitor,
  Source,
  Change,
  Analysis,
  Alert,
  Partnership,
  NewsItem,
  DashboardStats,
  PaginatedResponse,
  ActivityLogEntry,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

// Dashboard
export const getDashboard = () =>
  api.get<DashboardStats>('/dashboard').then(r => r.data);

// Competitors
export const getCompetitors = () =>
  api.get<Competitor[]>('/competitors').then(r => r.data);

export const getCompetitor = (slug: string) =>
  api.get<Competitor>(`/competitors/${slug}`).then(r => r.data);

export const createCompetitor = (data: {
  name: string;
  domain: string;
  slug?: string;
  industry?: string;
  description?: string;
  tags?: string[];
}) => api.post<Competitor>('/competitors', data).then(r => r.data);

export const deleteCompetitor = (slug: string) =>
  api.delete(`/competitors/${slug}`).then(r => r.data);

// Sources
export const getSources = (params?: Record<string, string>) =>
  api.get<Source[]>('/sources', { params }).then(r => r.data);

export const createSource = (data: {
  competitor_id: string;
  url: string;
  page_type?: string;
  scrape_method?: string;
  schedule_group?: string;
}) => api.post<Source>('/sources', data).then(r => r.data);

export const deleteSource = (id: string) =>
  api.delete(`/sources/${id}`).then(r => r.data);

// Changes
export const getChanges = (params?: Record<string, string | number>) =>
  api.get<PaginatedResponse<Change>>('/changes', { params }).then(r => r.data);

export const getChange = (id: string) =>
  api.get<Change>(`/changes/${id}`).then(r => r.data);

// Analyses
export const getAnalyses = (params?: Record<string, string | number>) =>
  api.get<Analysis[]>('/analyses', { params }).then(r => r.data);

// Alerts
export const getAlerts = (params?: Record<string, string | number>) =>
  api.get<Alert[]>('/alerts', { params }).then(r => r.data);

// Partnerships
export const getPartnerships = (params?: Record<string, string>) =>
  api.get<Partnership[]>('/partnerships', { params }).then(r => r.data);

// News
export const getNews = (params?: Record<string, string | number>) =>
  api.get<NewsItem[]>('/news', { params }).then(r => r.data);

// Scan
export const triggerScan = () =>
  api.post<{ status: string; scan_id: string; sources_scraped: number; changes_found: number; errors: string[] }>('/scan', {}, { timeout: 120000 }).then(r => r.data);

// Activity Log
export const getActivity = (limit = 30) =>
  api.get<ActivityLogEntry[]>('/activity', { params: { limit } }).then(r => r.data);

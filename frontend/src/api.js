import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'

const client = axios.create({ baseURL: BASE, timeout: 30000 })

export async function sendChat(text, lang) {
  const { data } = await client.post('/chat', { text, lang: lang || undefined })
  return data
}

export async function uploadPrescription(file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post('/prescription', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function getFacilities() {
  const { data } = await client.get('/facilities')
  return data
}

export async function getEmergencyInfo(lang = 'en') {
  const { data } = await client.get(`/emergency-info?lang=${lang}`)
  return data
}

export async function getHealth() {
  const { data } = await client.get('/health')
  return data
}

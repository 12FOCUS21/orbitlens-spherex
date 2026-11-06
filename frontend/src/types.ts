export interface Preset { id: string; name: string; cached: boolean; frame_count: number }
export interface Target { name: string; main_id?: string; ra_deg: number; dec_deg: number; coordinate_epoch_jyear: number | null }
export interface Job {
  job_id: string
  status: 'queued' | 'resolving' | 'searching' | 'ready' | 'partial' | 'empty' | 'error'
  message: string
  queue_position: number
  manifest_url: string | null
  target: Target | null
  cached: boolean
}
export interface Frame {
  image_url: string; fits_url: string; mjd: number; date_utc: string
  detector: string; collection: string; cutout_url: string
  quality: { valid_coverage: number; center_pixel_valid: boolean; center_pixel_flag_names: string[] }
  wavelength_at_target: { central_um: number | null; width_um: number | null }
}
export interface Manifest {
  status: string; detector: string; created_at_utc: string
  parameters: { ra: number; dec: number; fov: number }
  frames: Frame[]; warnings?: string[]; caveats: string[]; credit: string
  requested_count_reached?: boolean
  queries: Record<string, { rows?: number; possibly_truncated?: boolean; error?: string; retrieved_at_utc?: string }>
  failures: { error: string }[]
}

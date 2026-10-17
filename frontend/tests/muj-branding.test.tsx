import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { Campus } from '../src/api/client'
import { CampusOpening } from '../src/features/public/PublicExperience'

const muj = { id: 'muj', code: 'MUJ', name: 'Manipal University Jaipur', is_demo: false } as Campus
const demo = { id: 'demo', code: 'DEMO', name: 'Demo Campus', is_demo: true } as Campus
const props = { campuses: [demo, muj], locked: false, onCampus: vi.fn(), online: true, connected: true }

it('uses metadata for MUJ branding and retains title, actions, selector and source qualifications', () => {
  const { container } = render(<CampusOpening {...props} campus={muj} />)
  expect(screen.getByRole('heading', { name: 'Find your way across campus.' })).toBeVisible()
  expect(screen.getByRole('link', { name: 'Explore campus' })).toHaveAttribute('href', '#explorer')
  expect(screen.getByRole('link', { name: /About the data/ })).toHaveAttribute('href', '#about')
  expect(screen.getByText('Campus service connected')).toBeVisible()
  expect(screen.getByText(/Student project · not an official university service/)).toBeVisible()
  const logo = screen.getByAltText('Manipal University Jaipur emblem')
  expect(logo).toHaveAttribute('src', '/branding/muj/originals/muj_logo.png')
  expect(logo).toHaveAttribute('width', '250'); expect(logo).toHaveAttribute('height', '289')
  const photo = container.querySelector('.muj-hero-photo img')!
  expect(photo).toHaveAttribute('alt', '')
  expect(photo.closest('[aria-hidden]')).toHaveAttribute('aria-hidden', 'true')
  expect(photo).toHaveAttribute('loading', 'eager'); expect(photo).toHaveAttribute('fetchpriority', 'high')
  expect(container.querySelector('source')).toHaveAttribute('media', '(max-width: 760px)')
  fireEvent.change(screen.getByLabelText('Explore campus'), { target: { value: demo.id } })
  expect(props.onCampus).toHaveBeenCalledWith(demo.id)
})

it('never applies university assets to Demo, other campuses, or a name-only match', () => {
  const { container, rerender } = render(<CampusOpening {...props} campus={demo} />)
  for (const campus of [demo, { ...muj, is_demo: true }, { ...muj, code: 'OTHER' }]) {
    rerender(<CampusOpening {...props} campus={campus} />)
    expect(container.querySelector('picture')).toBeNull()
    expect(screen.queryByAltText('Manipal University Jaipur emblem')).not.toBeInTheDocument()
    if (campus.is_demo) expect(screen.getByText('Synthetic demo.')).toBeVisible()
  }
  rerender(<CampusOpening {...props} />)
  expect(container.querySelector('picture')).toBeNull()
})

it('keeps content and QR selector locking after photo and emblem errors, without focus changes', () => {
  const { container } = render(<CampusOpening {...props} campus={muj} locked />)
  const action = screen.getByRole('link', { name: 'Explore campus' })
  action.focus()
  fireEvent.error(container.querySelector('.muj-hero-photo img')!)
  fireEvent.error(screen.getByAltText('Manipal University Jaipur emblem'))
  expect(container.querySelector('.muj-hero-photo')).toHaveAttribute('data-photo-status', 'unavailable')
  expect(screen.getByText('University emblem unavailable')).toBeVisible()
  expect(screen.getByLabelText('Explore campus')).toBeDisabled()
  expect(screen.getByText('Campus service connected')).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Find your way across campus.' })).toBeVisible()
  expect(action).toHaveFocus()
})

it('resets visual failures when changing campus without changing status or source controls', () => {
  const { container, rerender } = render(<CampusOpening {...props} campus={muj} />)
  fireEvent.error(container.querySelector('.muj-hero-photo img')!)
  rerender(<CampusOpening {...props} campus={demo} online={false} />)
  expect(screen.getByText('Offline · connection needed for new routes')).toBeVisible()
  expect(screen.getByText('Synthetic demo.')).toBeVisible()
  rerender(<CampusOpening {...props} campus={muj} />)
  expect(container.querySelector('.muj-hero-photo img')).toBeInTheDocument()
})

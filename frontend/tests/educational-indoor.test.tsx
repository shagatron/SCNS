import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { api, type Campus } from '../src/api/client'
import EducationalIndoor from '../src/features/educational/EducationalIndoor'
import { CampusOpening } from '../src/features/public/PublicExperience'

vi.mock('../src/api/client', () => ({api: vi.fn()}))
vi.mock('../src/features/maps/FloorRouteMap', () => ({default: ({floor}: {floor:{label:string}}) => <p>Viewer: {floor.label}</p>}))
const id = (n:number) => `00000000-0000-4000-8000-${String(n).padStart(12,'0')}`
const floors = [0,1].map(n => ({id:id(n+1), label:n?'First floor':'Ground floor', frame_id:id(n+10)}))
const rooms = [{id:id(20), name:'Demo Classroom A',floor_id:floors[0].id},{id:id(21),name:'Demo Library',floor_id:floors[1].id}]
const data = {version:'indoor-school-v1',floors,rooms,source:'Original educational graph; production Dijkstra.'}
const clients:QueryClient[]=[]
function mount() { const client=new QueryClient({defaultOptions:{queries:{retry:false}}});clients.push(client);return render(<QueryClientProvider client={client}><EducationalIndoor /></QueryClientProvider>) }
beforeEach(()=>{vi.mocked(api).mockReset();history.replaceState(null,'','/indoor-demo')})
afterEach(()=>{cleanup();clients.splice(0).forEach(c=>c.clear());vi.restoreAllMocks()})

it('keeps the qualification visible while loading',()=>{
  vi.mocked(api).mockReturnValue(new Promise(()=>{}));mount()
  expect(screen.getAllByText('Demonstration layout — not an actual MUJ floorplan.')).toHaveLength(2)
  expect(screen.getByRole('status').textContent).toContain('Loading demonstration')
})
it('supports initial request failure and explicit recovery',async()=>{
  vi.mocked(api).mockRejectedValueOnce(new Error('Synthetic offline failure')).mockResolvedValue(data);mount()
  await screen.findByText('Synthetic offline failure')
  fireEvent.click(screen.getByRole('button',{name:'Retry demonstration'}))
  await screen.findByLabelText('Start room')
})
it('shows an empty state without a broken planner',async()=>{
  vi.mocked(api).mockResolvedValue({...data,rooms:[]});mount()
  await screen.findByText('No demonstration rooms available')
  expect(screen.queryByRole('button',{name:'Find demo directions'})).toBeNull()
})
it('does not claim measured distance or ETA and hides stale paths on selection edits',async()=>{
  const result={traversal_count:1,segments:[{edge_id:id(50),kind:'stairs',floor_id:floors[0].id,to_floor_id:floors[1].id,instruction:'Take Demo Stairs from Ground floor to First floor.'}],arrival_instruction:'Arrive at Demo Library.',distance_m:null,estimated_duration_s:null}
  vi.mocked(api).mockImplementation(async path => path.endsWith('/routes') ? result : data);mount()
  fireEvent.click(await screen.findByRole('button',{name:'Find demo directions'}))
  await screen.findByText('Computed demonstration route')
  expect(screen.getByText('Distance unknown · ETA unavailable')).toBeTruthy()
  expect(document.body.textContent).not.toMatch(/\b\d+\s*(metres|min)\b/)
  fireEvent.click(screen.getByRole('button',{name:'Show First floor'}))
  expect((screen.getByLabelText('View demonstration floor') as HTMLSelectElement).value).toBe(floors[1].id)
  fireEvent.change(screen.getByLabelText('Start room'),{target:{value:rooms[1].id}})
  expect(screen.queryByText('Computed demonstration route')).toBeNull()
  expect(location.search).not.toContain('route=1')
})
it('keeps a route error beside the planner and retains both selections',async()=>{
  vi.mocked(api).mockImplementation(async path=> {if(path.endsWith('/routes'))throw new Error('Synthetic no route');return data});mount()
  fireEvent.click(await screen.findByRole('button',{name:'Find demo directions'}))
  await screen.findByText('Synthetic no route')
  expect(screen.getByRole('alert').closest('#demo-planner')).toBeTruthy()
  expect((screen.getByLabelText('Start room') as HTMLSelectElement).value).toBe(rooms[0].id)
  expect((screen.getByLabelText('Destination room') as HTMLSelectElement).value).toBe(rooms[1].id)
})
it('adds the entry only to published MUJ metadata, keeping original actions',()=>{
  const campus:Campus={id:id(99),name:'MUJ preview',code:'MUJ',is_demo:false,timezone:'Asia/Kolkata',center:{type:'Point',coordinates:[75,26]},boundary:{type:'Polygon',coordinates:[[[75,26],[76,26],[76,27],[75,26]]]}}
  const props={campuses:[campus],locked:false,onCampus:vi.fn(),online:true,connected:true}
  const view=render(<CampusOpening {...props} campus={campus} />)
  expect(screen.getByRole('link',{name:'Indoor navigation demo ↗'}).getAttribute('href')).toContain('returnCampus='+campus.id)
  expect(screen.getByRole('link',{name:'Explore campus'})).toBeTruthy()
  expect(screen.getByRole('link',{name:'About the data'})).toBeTruthy()
  view.rerender(<CampusOpening {...props} campus={{...campus,is_demo:true}} />)
  expect(screen.queryByRole('link',{name:'Indoor navigation demo ↗'})).toBeNull()
})

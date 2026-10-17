export function focusPlanner(id: 'source' | 'destination') {
  window.dispatchEvent(new Event('explorer-open-planner'))
  const controls = document.querySelector<HTMLDetailsElement>('.route-controls')
  if (controls) controls.open = true
  requestAnimationFrame(() => document.getElementById(id)?.focus())
}

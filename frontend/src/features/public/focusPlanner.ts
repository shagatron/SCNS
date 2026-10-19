export function focusPlanner(id: 'source' | 'destination') {
  const controls = document.querySelector<HTMLDetailsElement>('.route-controls')
  if (controls) controls.open = true
  requestAnimationFrame(() => document.getElementById(id)?.focus())
}

import { gsap } from 'gsap';

export interface MotionController {
  enabled: () => boolean;
  duration: (seconds: number) => number;
  replay: () => void;
  pulseNodes: () => void;
}

/** Start visual behavior before the provisioning application is initialized. */
export function createMotionController(): MotionController {
  type Preference = 'auto' | 'on' | 'off';
  const reduced = typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-reduced-motion: reduce)')
    : undefined;
  // Every fresh visit starts animated, including browsers with an old Auto/Off
  // preference. The operator can change motion for the current page session.
  let preference: Preference = 'on';
  const enabled = () => preference === 'on' || (preference === 'auto' && !reduced?.matches);
  const duration = (seconds: number) => enabled() ? seconds : 0;
  const selector = document.getElementById('motion-preference') as HTMLSelectElement;
  const replayButton = document.getElementById('replay-motion') as HTMLButtonElement;
  const status = document.getElementById('motion-status')!;
  let flow: gsap.core.Timeline | undefined;
  let entrance: gsap.core.Tween | undefined;
  const cards = () => Array.from(document.querySelectorAll<HTMLElement>('.bento-card')).filter(card => !card.closest('[hidden]'));

  function pulseNodes() {
    gsap.fromTo('.node-orbit', { scale: enabled() ? .9 : 1 }, { scale: 1, duration: duration(.48), stagger: duration(.06), ease: 'back.out(1.6)', overwrite: true });
  }
  function replay() {
    entrance?.kill();
    gsap.set('.bento-card', { clearProps: 'opacity,transform' });
    if (!enabled()) return;
    entrance = gsap.fromTo(cards(), { opacity: 0, y: 22 }, { opacity: 1, y: 0, duration: .55, stagger: .045, ease: 'power3.out', clearProps: 'opacity,transform' });
    pulseNodes();
  }
  function configure(playEntrance: boolean) {
    flow?.kill();
    flow = undefined;
    document.documentElement.dataset.motion = preference;
    gsap.set('.data-packet', { attr: { 'stroke-dashoffset': 0 } });
    gsap.set('.packet-orb', { attr: { cx: 100 }, opacity: 0 });
    if (enabled()) {
      flow = gsap.timeline({ paused: document.hidden });
      flow.to('.data-packet', { attr: { 'stroke-dashoffset': -172 }, duration: 2.4, repeat: -1, ease: 'none' }, 0);
      document.querySelectorAll('.packet-orb').forEach((orb, index) => {
        flow!.fromTo(orb, { attr: { cx: 100 }, opacity: .95 }, { attr: { cx: 1100 }, opacity: .95, duration: 4.2, repeat: -1, ease: 'none' }, index * 1.05);
      });
    }
    const systemReduced = preference === 'auto' && reduced?.matches;
    status.textContent = `GSAP ${gsap.version} · ${systemReduced ? 'SYSTEM REDUCED' : enabled() ? 'ON' : 'OFF'}`;
    status.className = `pill small ${enabled() ? 'purple' : 'yellow'}`;
    status.title = systemReduced ? 'The system requests reduced motion. Motion On enables animation in this app.' : 'GSAP is running. Replay restarts the card entrance and topology pulse.';
    replayButton.disabled = !enabled();
    if (playEntrance || !enabled()) replay();
    document.documentElement.dataset.motionReady = 'true';
  }

  selector.value = preference;
  selector.addEventListener('change', () => {
    preference = selector.value as Preference;
    configure(true);
  });
  replayButton.addEventListener('click', () => configure(true));
  const updateSystemPreference = () => { if (preference === 'auto') configure(false); };
  if (typeof reduced?.addEventListener === 'function') reduced.addEventListener('change', updateSystemPreference);
  else reduced?.addListener?.(updateSystemPreference);

  function resumeVisibleFlow() {
    if (document.hidden) { flow?.pause(); return; }
    if (!enabled()) return;
    if (!flow) configure(false);
    gsap.ticker.wake();
    flow?.resume();
  }
  document.addEventListener('visibilitychange', resumeVisibleFlow);
  window.addEventListener('focus', resumeVisibleFlow);
  window.addEventListener('pagehide', () => {
    flow?.kill(); entrance?.kill();
    flow = undefined; entrance = undefined;
    // A back/forward-cache restore reuses this DOM; never leave cards mid-fade.
    gsap.set('.bento-card', { clearProps: 'opacity,transform' });
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) configure(false);
    resumeVisibleFlow();
  });
  configure(true);
  return { enabled, duration, replay, pulseNodes };
}

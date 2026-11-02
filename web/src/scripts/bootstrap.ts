import { createMotionController } from './motion';
import { initializeCommandCenter } from './command-center';

function start() {
  if (document.documentElement.dataset.frontendReady === 'true') return;
  try {
    // Visual startup is independent of API availability and provisioning state.
    const motion = createMotionController();
    initializeCommandCenter(motion);
    document.documentElement.dataset.frontendReady = 'true';
    document.getElementById('reload-workspace')!.hidden = true;
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown startup error';
    document.documentElement.dataset.frontendError = message;
    const details = document.getElementById('frontend-error-detail');
    if (details) details.textContent = message;
    const panel = document.getElementById('frontend-error');
    if (panel) panel.hidden = false;
    document.getElementById('reload-workspace')!.hidden = false;
    console.error('RELPOOL frontend startup failed:', error);
  }
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
else start();

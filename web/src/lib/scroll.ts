// Keep the newest message in view while an answer streams in. Scrolling up
// stops the follow; scrolling back to the bottom or asking a new question
// starts it again. Ported from app/web/scroll.js as a Svelte action on the thread.

const NEAR = 80; // px from the bottom that still counts as "at the bottom"

export function autoFollow(thread: HTMLElement) {
	let follow = true;
	let userInputAt = 0;

	const atBottom = () => window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - NEAR;
	const toBottom = () => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'auto' });

	// Only scrolls the user causes change the follow state, not our own.
	const markInput = () => (userInputAt = performance.now());
	const target = (e: Event) => e.target as Element | null;
	// A click on Ask or an example is not a scroll. Count only the scrollbar
	// and source links, which can scroll their chip into view.
	const pointerdown = (e: PointerEvent) => {
		if (e.clientX >= document.documentElement.clientWidth || target(e)?.closest?.('.cite, .sources a')) markInput();
	};
	const keydown = (e: KeyboardEvent) => {
		if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(e.key) && e.target === document.body)
			markInput();
		// Opening a source from the keyboard can scroll its chip into view.
		if ((e.key === 'Enter' || e.key === ' ') && target(e)?.closest?.('.cite, .sources a')) markInput();
	};
	const scroll = () => {
		if (performance.now() - userInputAt < 400) follow = atBottom();
	};

	for (const ev of ['wheel', 'touchmove']) window.addEventListener(ev, markInput, { passive: true });
	window.addEventListener('pointerdown', pointerdown, { passive: true });
	window.addEventListener('keydown', keydown);
	window.addEventListener('scroll', scroll, { passive: true });

	let queued = false;
	let raf = 0;
	const observer = new MutationObserver((records) => {
		for (const r of records) {
			for (const n of r.addedNodes) if ((n as Element).classList?.contains('user')) follow = true;
		}
		// The source panel locks the page behind it on narrow screens.
		if (!follow || queued || document.body.classList.contains('panel-open')) return;
		queued = true;
		raf = requestAnimationFrame(() => {
			queued = false;
			// An emptied thread (New chat) stays at the top, where the reset put it.
			if (!thread.querySelector('.msg')) return;
			if (follow) toBottom();
		});
	});
	observer.observe(thread, { childList: true, subtree: true, characterData: true });

	return {
		destroy() {
			observer.disconnect();
			cancelAnimationFrame(raf);
			for (const ev of ['wheel', 'touchmove']) window.removeEventListener(ev, markInput);
			window.removeEventListener('pointerdown', pointerdown);
			window.removeEventListener('keydown', keydown);
			window.removeEventListener('scroll', scroll);
		}
	};
}

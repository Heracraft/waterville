// Chat session state shared by Header (New chat), Chat (thread, ask bar) and
// SourcePanel. Ported from the chat half of app/web/app.js.

import { streamChat, type ChatFilters, type ChatMeta, type ChatMode, type ChatTurn, type Source } from './api';

export type UserMessage = { id: number; role: 'user'; text: string };

export type BotMessage = {
	id: number;
	role: 'bot';
	question: string;
	answer: string;
	sources: Source[];
	meta: ChatMeta | null;
	/** loading: no text yet; streaming: text arriving; done: finished (maybe with error). */
	status: 'loading' | 'streaming' | 'done';
	error: string | null;
	loadingLabel: string;
	/** Other SSE events by name, e.g. the public `checklist` and `triage` cards (A1, A2). */
	extras?: Record<string, unknown>;
};

export type Message = UserMessage | BotMessage;

/** The open source: which message, which source number, and which chip (occ) or sources-list link (null). */
export type ActiveSource = { msgId: number; n: number; occ: number | null; trigger: HTMLElement };

export type ChatOptions = {
	mode?: ChatMode;
	/** Read on every ask, so a page can bind filters to its controls. */
	filters?: () => ChatFilters | undefined;
	caseId?: () => string | undefined;
	/** Called after each answer finishes without a fatal error. */
	onAnswer?: (msg: BotMessage) => void;
};

export const LOADING_LABEL = 'Searching the City Code and state law';
export const NETWORK_ERROR = 'Could not reach the server. Check your connection and ask again.';
/** The server trims earlier answers to this length before the model sees them. */
const HISTORY_ANSWER_CHARS = 2000;

/** Plain copy for a failed request: fetch rejects with a TypeError when the network is gone. */
export function failureText(e: unknown): string {
	if (e instanceof TypeError) return NETWORK_ERROR;
	return e instanceof Error ? e.message : String(e);
}

let nextId = 1;

export class ChatSession {
	messages = $state<Message[]>([]);
	busy = $state(false);
	active = $state<ActiveSource | null>(null);
	/** True while the source panel covers the page (narrow screens); header and main go inert. */
	modal = $state(false);
	/** Bumped by clear() so the page can reset scroll and focus. */
	resets = $state(0);

	history: ChatTurn[] = [];
	options: ChatOptions;
	private inflight: AbortController | null = null;

	constructor(options: ChatOptions = {}) {
		this.options = options;
	}

	get started() {
		return this.messages.length > 0;
	}

	bot(id: number): BotMessage | undefined {
		const m = this.messages.find((x) => x.id === id);
		return m && m.role === 'bot' ? m : undefined;
	}

	async ask(question: string): Promise<BotMessage | undefined> {
		this.busy = true;
		this.messages.push({ id: nextId++, role: 'user', text: question });
		this.history.push({ role: 'user', content: question });
		this.messages.push({
			id: nextId++,
			role: 'bot',
			question,
			answer: '',
			sources: [],
			meta: null,
			status: 'loading',
			error: null,
			loadingLabel: LOADING_LABEL,
			extras: {}
		});
		// The proxied object, so writes below update the view.
		const bot = this.messages[this.messages.length - 1] as BotMessage;
		let failed: string | null = null;
		const ctrl = (this.inflight = new AbortController());
		const { mode, filters, caseId } = this.options;
		const f = filters?.();
		const c = caseId?.();

		try {
			const events = streamChat(
				{
					messages: this.history.slice(-6),
					...(mode && mode !== 'public' ? { mode } : {}),
					...(f && (f.chapters?.length || f.source_types?.length) ? { filters: f } : {}),
					...(c ? { case_id: c } : {})
				},
				ctrl.signal
			);
			for await (const ev of events) {
				if (ev.event === 'meta') bot.meta = ev.data as ChatMeta;
				else if (ev.event === 'sources') {
					const list = ev.data as Source[];
					bot.sources = list;
					if (!bot.answer && list.length)
						bot.loadingLabel = `Reading ${list.length} matching section${list.length === 1 ? '' : 's'}`;
				} else if (ev.event === 'delta') {
					bot.answer += (ev.data as { text: string }).text;
					bot.status = 'streaming';
				} else if (ev.event === 'error') failed = (ev.data as { message: string }).message;
				else if (ev.event !== 'done' && bot.extras) bot.extras[ev.event] = ev.data;
			}
		} catch (e) {
			failed = failureText(e);
		}
		// Cleared while streaming: the thread and history are already reset.
		if (ctrl.signal.aborted) return;
		this.inflight = null;

		bot.status = 'done';
		bot.error = failed;
		if (failed && !bot.answer) this.history.pop();
		else {
			this.history.push({ role: 'assistant', content: bot.answer.slice(0, HISTORY_ANSWER_CHARS) });
			this.options.onAnswer?.(bot);
		}
		this.busy = false;
		return bot;
	}

	clear() {
		this.inflight?.abort();
		this.inflight = null;
		this.active = null;
		this.messages = [];
		this.history.length = 0;
		this.busy = false;
		this.resets++;
	}
}

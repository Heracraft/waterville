<script lang="ts">
	// A5: a printable complaint sheet to bring to a Code Enforcement
	// appointment. Client side only: nothing is sent to the server and
	// nothing is stored in the browser. Reloading the page clears it.
	import Header from '$lib/components/Header.svelte';
	import PublicToolNav from '$lib/components/PublicToolNav.svelte';
	import {
		CONCERNS,
		RELATIONS,
		emptyComplaint,
		isUrgent,
		longDate,
		missing,
		telHref,
		type Complaint
	} from '$lib/components/PublicData';

	const PHONE = '207-680-4208';
	let c = $state<Complaint>(emptyComplaint());
	const urgent = $derived(isUrgent(c));
	const gaps = $derived(missing(c));
	const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
	const concernLabels = $derived(CONCERNS.filter((x) => c.concerns.includes(x.id)).map((x) => x.label));

	function clear() {
		if (confirm('Clear everything on this sheet?')) c = emptyComplaint();
	}
</script>

<svelte:head>
	<title>Complaint sheet | Waterville Codes RAG</title>
</svelte:head>

<Header title="Complaint sheet" compact>
	{#snippet actions()}
		<a class="theme-toggle" href="/">Ask a question</a>
	{/snippet}
</Header>
<main class="wrap complaint">
	<div class="page-head no-print">
		<p class="page-lede">
			Write down a property concern before your appointment with Code Enforcement, then print the sheet and bring it with
			your photos. Nothing you type leaves this page or is saved. Reloading the page clears it.
		</p>
	</div>

	<section class="sheet steps no-print" aria-labelledby="how">
		<h2 id="how">How complaints work</h2>
		<ol>
			<li>Call the Code Enforcement Officer to book an appointment: <a href={telHref(PHONE)}>{PHONE}</a>, Monday to Thursday, 7:00 a.m. to 5:00 p.m.</li>
			<li>Bring this sheet and your photos. The office will have you fill out its own complaint form; this sheet keeps the facts in front of you.</li>
			<li>For danger to life right now, such as fire, a gas smell or a collapse, call 911. Do not wait for an appointment.</li>
		</ol>
	</section>

	{#if urgent}
		<div class="urgent no-print" role="alert">
			<strong>This may not be able to wait for an appointment.</strong>
			No heat, sewage, structural damage, fire hazards, unsafe wiring and no water are life safety matters. Call Code
			Enforcement now at <a href={telHref(PHONE)}>{PHONE}</a>, or call 911 if anyone is in danger.
		</div>
	{/if}

	<form class="fill no-print" onsubmit={(e) => e.preventDefault()} autocomplete="off">
		<fieldset class="sheet">
			<legend>The property</legend>
			<div class="two">
				<label class="field"><span>Street address of the property</span><input bind:value={c.address} required /></label>
				<label class="field"><span>Unit or apartment (if any)</span><input bind:value={c.unit} /></label>
				<label class="field"
					><span>Map and lot (if known)</span><input bind:value={c.mapLot} /><span class="help"
						>From the city's online tax map.</span
					></label
				>
				<label class="field"><span>Owner or landlord (if known)</span><input bind:value={c.owner} /></label>
			</div>
		</fieldset>

		<fieldset class="sheet">
			<legend>The concern</legend>
			<div class="concerns">
				{#each CONCERNS as k (k.id)}
					<label class="check">
						<input type="checkbox" value={k.id} bind:group={c.concerns} />
						<span>{k.label}</span>
					</label>
				{/each}
			</div>
			<label class="field">
				<span>What you saw</span>
				<textarea bind:value={c.description} rows="6" placeholder="Where on the property, what it looks like, how it affects you or others."
				></textarea>
			</label>
			<div class="two">
				<label class="field"><span>First noticed</span><input type="date" bind:value={c.firstSeen} /></label>
				<label class="field"><span>Last seen</span><input type="date" bind:value={c.lastSeen} /></label>
				<label class="field">
					<span>Is it still going on?</span>
					<select bind:value={c.ongoing}>
						<option value="">Choose</option>
						<option>Yes</option>
						<option>No</option>
						<option>Not sure</option>
					</select>
				</label>
				<label class="field">
					<span>Have you told the owner or landlord?</span>
					<input bind:value={c.ownerContacted} placeholder="When, how, and what they said" />
				</label>
			</div>
			<label class="field">
				<span>Photos you will bring</span>
				<textarea bind:value={c.photos} rows="3" placeholder="For example: 3 photos of the porch, taken September 28."></textarea>
			</label>
			<label class="field">
				<span>Who else is affected, or saw it</span>
				<input bind:value={c.others} />
			</label>
		</fieldset>

		<fieldset class="sheet">
			<legend>You</legend>
			<p class="help">So the office can reach you about the complaint.</p>
			<div class="two">
				<label class="field"><span>Name</span><input bind:value={c.name} autocomplete="name" /></label>
				<label class="field"><span>Phone</span><input bind:value={c.phone} type="tel" autocomplete="tel" /></label>
				<label class="field"><span>Email</span><input bind:value={c.email} type="email" autocomplete="email" /></label>
				<label class="field">
					<span>You are</span>
					<select bind:value={c.relation}>
						<option value="">Choose</option>
						{#each RELATIONS as r (r)}<option>{r}</option>{/each}
					</select>
				</label>
			</div>
			<label class="field"><span>Mailing address</span><input bind:value={c.mailing} autocomplete="street-address" /></label>
		</fieldset>

		<div class="actions">
			{#if gaps.length}
				<p class="muted">Still needed: {gaps.join(', ')}.</p>
			{:else}
				<p class="muted">The sheet has the essentials.</p>
			{/if}
			<p class="btn-row">
				<button type="button" class="btn" onclick={() => window.print()}>Print the sheet</button>
				<button type="button" class="btn secondary" onclick={clear}>Clear</button>
			</p>
		</div>
	</form>

	<h2 class="preview-title no-print">Preview</h2>
	<article class="paper" aria-label="Printable complaint sheet">
		<header class="paper-head">
			<p class="paper-kicker">To the Code Enforcement Office, 7 College Avenue, Waterville, Maine 04901</p>
			<h2>Property concern</h2>
			<p class="paper-meta">Prepared {today} by the resident for an appointment. Not an official city form.</p>
		</header>

		<table class="ledger">
			<tbody>
				<tr><th scope="row">Property address</th><td>{c.address}{c.unit ? `, ${c.unit}` : ''}</td></tr>
				<tr><th scope="row">Map and lot</th><td>{c.mapLot}</td></tr>
				<tr><th scope="row">Owner or landlord</th><td>{c.owner}</td></tr>
				<tr><th scope="row">Concern</th><td>{concernLabels.join('; ')}</td></tr>
				<tr><th scope="row">What I saw</th><td class="pre">{c.description}</td></tr>
				<tr><th scope="row">First noticed</th><td>{longDate(c.firstSeen)}</td></tr>
				<tr><th scope="row">Last seen</th><td>{longDate(c.lastSeen)}</td></tr>
				<tr><th scope="row">Still going on</th><td>{c.ongoing}</td></tr>
				<tr><th scope="row">Owner or landlord told</th><td>{c.ownerContacted}</td></tr>
				<tr><th scope="row">Photos</th><td class="pre">{c.photos}</td></tr>
				<tr><th scope="row">Others affected</th><td>{c.others}</td></tr>
			</tbody>
		</table>

		<table class="ledger">
			<tbody>
				<tr><th scope="row">My name</th><td>{c.name}</td></tr>
				<tr><th scope="row">I am</th><td>{c.relation}</td></tr>
				<tr><th scope="row">Phone</th><td>{c.phone}</td></tr>
				<tr><th scope="row">Email</th><td>{c.email}</td></tr>
				<tr><th scope="row">Mailing address</th><td>{c.mailing}</td></tr>
			</tbody>
		</table>

		<div class="sign">
			<span>Signature</span>
			<span>Date</span>
		</div>

		<div class="office">
			<p><strong>For office use</strong></p>
			<p>Received by ________________ Date ________ Case number ________________</p>
		</div>
	</article>
</main>

<PublicToolNav />

<style>
	.steps h2,
	.preview-title {
		font: 300 1.3rem/1.3 var(--serif);
		margin: 0 0 10px;
	}
	.steps ol {
		margin: 0;
		padding-left: 22px;
	}
	.steps li {
		margin-bottom: 6px;
	}
	.steps li::marker {
		color: var(--accent);
	}
	.urgent {
		margin: 20px 0;
		padding: 14px 16px;
		border: 1px solid var(--accent);
		border-left: 4px solid var(--accent);
		background: var(--surface);
	}
	.urgent strong {
		display: block;
		color: var(--accent);
		margin-bottom: 4px;
	}
	.fill {
		margin-top: 20px;
	}
	fieldset.sheet {
		margin: 0 0 20px;
		min-width: 0;
	}
	legend {
		padding: 0 6px;
		margin-left: -6px;
		font: 300 1.3rem var(--serif);
		color: var(--text);
	}
	.two {
		display: grid;
		gap: 0 16px;
	}
	@media (min-width: 760px) {
		.two {
			grid-template-columns: 1fr 1fr;
		}
	}
	.concerns {
		display: grid;
		gap: 2px 16px;
		margin-bottom: 16px;
	}
	@media (min-width: 760px) {
		.concerns {
			grid-template-columns: 1fr 1fr;
		}
	}
	.concerns .check {
		padding: 4px 0;
		font-size: 0.95rem;
	}
	.actions {
		margin-bottom: 28px;
	}
	.actions .muted {
		margin: 0 0 10px;
	}
	.paper {
		background: var(--surface);
		border: 1px solid var(--rule);
		border-top: 3px solid var(--accent);
		padding: 24px;
		color: var(--text);
	}
	.paper-head {
		margin-bottom: 16px;
		padding-bottom: 12px;
		border-bottom: 1px solid var(--rule);
	}
	.paper-head h2 {
		margin: 4px 0;
		font: 300 1.8rem/1.2 var(--serif);
	}
	.paper-kicker,
	.paper-meta {
		margin: 0;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.paper .ledger {
		margin-bottom: 16px;
	}
	.paper .ledger th {
		width: 32%;
	}
	.paper .ledger td {
		min-height: 1.4em;
		overflow-wrap: anywhere;
	}
	.pre {
		white-space: pre-wrap;
	}
	.sign {
		display: grid;
		grid-template-columns: 2fr 1fr;
		gap: 24px;
		margin: 32px 0 20px;
	}
	.sign span {
		border-top: 1px solid var(--rule);
		padding-top: 4px;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.office {
		border: 1px dashed var(--rule);
		padding: 10px 14px;
		font-size: 0.85rem;
	}
	.office p {
		margin: 0 0 6px;
	}
	@media (max-width: 640px) {
		.paper {
			padding: 16px;
		}
		.paper .ledger th {
			width: 40%;
		}
	}
	@media print {
		.paper {
			border: 0;
			padding: 0;
			background: #fff;
			color: #000;
		}
		.paper :global(*) {
			color: #000 !important;
			background: #fff !important;
		}
		.paper .ledger,
		.paper .ledger th,
		.paper .ledger td {
			border-color: #000 !important;
		}
	}
</style>

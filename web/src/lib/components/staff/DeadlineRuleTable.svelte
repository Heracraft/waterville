<script lang="ts">
	// The whole rule table, for review by the CEO: every clock with its trigger,
	// offset, counting rule, citation and verification status.
	import { STATUS_TEXT, statusOf, type RuleTable } from './DeadlineData';

	let { table }: { table: RuleTable } = $props();

	let show = $state<'all' | 'verified' | 'check' | 'unverified'>('all');
	const triggerLabel = $derived(new Map(table.triggers.map((t) => [t.id, t.label])));
	const rows = $derived(table.rules.filter((r) => show === 'all' || statusOf(r) === show));
	const counts = $derived({
		verified: table.rules.filter((r) => statusOf(r) === 'verified').length,
		check: table.rules.filter((r) => statusOf(r) === 'check').length,
		unverified: table.rules.filter((r) => statusOf(r) === 'unverified').length
	});
	const uid = $props.id();
</script>

<div class="rt">
	<div class="bar">
		<label class="field inline" for="{uid}-f">
			<span>Show</span>
			<select id="{uid}-f" bind:value={show}>
				<option value="all">All {table.rules.length} rules</option>
				<option value="verified">Verified ({counts.verified})</option>
				<option value="check">Text verified, application to check ({counts.check})</option>
				<option value="unverified">Unverified ({counts.unverified})</option>
			</select>
		</label>
	</div>
	<div class="table-scroll">
		<table class="ledger">
			<thead>
				<tr>
					<th scope="col">Clock</th>
					<th scope="col">Starts from</th>
					<th scope="col">Offset</th>
					<th scope="col">Counting</th>
					<th scope="col">Citation</th>
					<th scope="col">Status</th>
				</tr>
			</thead>
			<tbody>
				{#each rows as r (r.id)}
					<tr>
						<td>{r.label}</td>
						<td>{r.triggers.map((t) => triggerLabel.get(t) ?? t).join('; ')}</td>
						<td class="nowrap">{r.offset}</td>
						<td>{table.conventions[r.convention]?.label ?? r.convention}</td>
						<td><a href={r.url} target="_blank" rel="noopener noreferrer">{r.citation}</a></td>
						<td class="st st-{statusOf(r)}">{STATUS_TEXT[statusOf(r)]}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.bar {
		display: flex;
		justify-content: flex-end;
		margin-bottom: 10px;
	}
	.field.inline {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
	}
	.field.inline select {
		width: auto;
		padding: 5px 10px;
		font-size: 0.88rem;
	}
	table {
		min-width: 760px;
		font-size: 0.86rem;
	}
	td a {
		color: var(--text);
		text-decoration-color: var(--accent);
	}
	.nowrap {
		white-space: nowrap;
	}
	.st {
		font-weight: 600;
	}
	.st-verified {
		color: var(--muted);
	}
	.st-check,
	.st-unverified {
		color: var(--accent);
	}
</style>

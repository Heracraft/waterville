<script lang="ts">
	// A case selector for other staff pages (research desk "save to case",
	// deadline calculator, drafts). Lists open and monitoring cases, newest
	// change first. Bind `value` to the chosen case id ('' for none).
	//
	//   <CasePicker bind:value={caseId} />
	//   await cases.addItem(caseId, { kind: 'deadline', label, date, citation });
	import { cases, caseHeading, type Case } from './CaseData';

	let {
		value = $bindable(''),
		label = 'Case',
		none = 'No case',
		includeClosed = false
	}: { value?: string; label?: string; none?: string; includeClosed?: boolean } = $props();

	let list = $state<Case[]>([]);
	let error = $state('');
	const uid = $props.id();

	$effect(() => {
		const closed = includeClosed;
		cases
			.list({ status: closed ? 'all' : '' })
			.then((r) => {
				list = closed ? r.cases : r.cases.filter((c) => c.status !== 'closed');
				error = '';
			})
			.catch((e) => (error = e instanceof Error ? e.message : String(e)));
	});

	// Keep a preselected id (from ?case=) visible even before the list loads.
	const known = $derived(!value || list.some((c) => c.id === value));
</script>

<label class="field case-picker" for="{uid}-sel">
	<span>{label}</span>
	<select id="{uid}-sel" bind:value>
		<option value="">{none}</option>
		{#if !known}<option value={value}>Case {value}</option>{/if}
		{#each list as c (c.id)}
			<option value={c.id}>{caseHeading(c)} ({c.id})</option>
		{/each}
	</select>
	{#if error}<span class="help error-text">Could not load cases: {error}</span>{/if}
</label>

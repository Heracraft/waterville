(function () {
  // ---------------------------------------------------------------- data
  var DOCS = [
    { id: 'charter', name: 'City Charter', force: 'binding', cov: 'full', eg: 'Charter Art. IV, § 9', covers: 'The structure of the city government.' },
    { id: 'ord', name: 'City ordinances', force: 'binding', cov: 'full', eg: '§ 275-4.26', covers: '38 chapters: zoning, property maintenance, building, rentals, floodplains, licenses.' },
    { id: 'newlaw', name: 'New laws', force: 'binding', cov: 'full', eg: 'Adopted ordinance not yet in the Code', covers: 'Recent changes to the City Code.' },
    { id: 'attach', name: 'Code attachments', force: 'binding', cov: 'full', eg: 'Ch. 173 Appendix A fee schedule', covers: 'Fee schedules, appendices, committee charges.' },
    { id: 'forms', name: 'City forms', force: 'procedure', cov: 'partial', eg: 'Building Permit Application', covers: 'What an applicant submits, inspections, printed fees. In the preview only.' },
    { id: 'stat', name: 'Maine statutes', force: 'binding', cov: 'partial', eg: '30-A M.R.S. § 4452', covers: 'Inspector powers, penalties, appeals, dangerous buildings. Some sections.' },
    { id: 'rules', name: 'State rules', force: 'binding', cov: 'full', eg: '10-144 CMR ch. 241', covers: 'Building code adoption, septic systems, shoreland zoning, certification.' },
    { id: 'model', name: 'ICC model codes', force: 'binding', cov: 'ref', eg: '2021 IRC, 2021 IECC', covers: 'Structure, exits, fire separation, energy, mechanical. Binding after state adoption.' },
    { id: 'std', name: 'Referenced standards', force: 'binding', cov: 'ref', eg: 'NFPA 101, NEC, ASHRAE 90.1', covers: 'Life safety, electrical, plumbing, ventilation, test methods. Binding after adoption.' },
    { id: 'court', name: 'Court rules', force: 'procedure', cov: 'partial', eg: 'M.R. Civ. P. 80K', covers: 'Land use citations (80K), appeals (80B), inspection warrants (80E). In the preview only.' },
    { id: 'case', name: 'Case law', force: 'binding', cov: 'none', eg: 'Mills v. Eliot, 2008 ME 134', covers: 'How courts interpret statutes and ordinances.' },
    { id: 'manual', name: 'Guidance manuals', force: 'advisory', cov: 'full', eg: 'Court Rule 80K Manual (2017)', covers: 'How to inspect, enforce and write decisions. Some parts are old.' },
    { id: 'notes', name: 'Staff notes', force: 'advisory', cov: 'partial', eg: '16-642 CMR is now 08-003 CMR', covers: 'New rule numbers, old editions, penalty levels. Staff only, reviewed by the inspector.' }
  ];
  var FORCE = { binding: 'Binding', procedure: 'Procedure', advisory: 'Advisory' };
  var COV = { full: 'Full text', partial: 'Some text or preview only', ref: 'Name and link only (copyright)', none: 'Not included' };

  var ENTS = [
    { g: 'City of Waterville', id: 'council', name: 'City Council', does: 'Adopts ordinances and fee schedules. Gives staff permission to go to court.', makes: ['charter', 'ord', 'newlaw', 'attach'] },
    { g: 'City of Waterville', id: 'ceo', name: 'Code Enforcement Office', key: true, does: 'Three staff: Director Dan Bradstreet, CEO Adam Bradstreet, Ordinance Compliance Officer Todd Buckmore. Issues permits, inspects, enforces.', makes: ['forms'], decides: 'Permits, certificates of occupancy, notices of violation' },
    { g: 'City of Waterville', id: 'pb', name: 'Planning Board', does: 'Reviews site plans, subdivisions and shoreland applications.', makes: [], decides: 'Site plan, subdivision and shoreland approvals' },
    { g: 'City of Waterville', id: 'bza', name: 'Board of Zoning Appeals', does: 'Hears appeals of inspector decisions filed within 30 days. Makes a new decision on the full facts. Gives variances.', makes: [], decides: 'Appeals and variances (§ 275-6.2)' },
    { g: 'City of Waterville', id: 'fire', name: 'Fire Department', does: 'Life safety review on permits. Rental registry. Business license and short-term rental inspections.', makes: ['forms'] },
    { g: 'City of Waterville', id: 'sol', name: 'City Solicitor', does: 'The lawyer for the city. Handles court cases and legal questions.', makes: [], decides: 'Legal opinions, court filings' },
    { g: 'City of Waterville', id: 'ep', name: 'Electrical and plumbing inspectors', does: 'Electrical inspector for one- and two-family houses (§ 127-9). Plumbing inspector for plumbing and septic permits. Names not published.', makes: [], decides: 'Electrical and plumbing permits' },
    { g: 'State of Maine', id: 'leg', name: 'Maine Legislature', does: 'Writes the Maine Revised Statutes. Title 30-A sets inspector duties, powers and penalties.', makes: ['stat'] },
    { g: 'State of Maine', id: 'moca', name: 'Office of Community Affairs (MOCA)', does: 'Trains and certifies inspectors (before: DECD). Publishes building code and certification rules and the manuals.', makes: ['rules', 'manual'] },
    { g: 'State of Maine', id: 'sfm', name: 'State Fire Marshal', does: 'Enforces NFPA 101 for the state. Construction and accessibility permits for many commercial and multifamily buildings.', makes: ['rules'] },
    { g: 'State of Maine', id: 'dep', name: 'Environmental Protection (DEP)', does: 'Writes shoreland zoning rules that each town must follow. Reviews work near protected resources.', makes: ['rules'] },
    { g: 'State of Maine', id: 'dhhs', name: 'Health and Human Services (DHHS)', does: 'Writes the septic system rule and the HHE-200 form.', makes: ['rules'] },
    { g: 'State of Maine', id: 'boards', name: 'Licensing boards', does: 'Plumbing and electrical boards adopt the plumbing code and the National Electrical Code.', makes: ['rules'] },
    { g: 'Courts', id: 'dc', name: 'District Court', does: 'Hears Rule 80K land use citations. This is how the city gets civil penalties.', makes: ['case'] },
    { g: 'Courts', id: 'sc', name: 'Superior Court', does: 'Hears Rule 80B appeals of board decisions.', makes: ['case'] },
    { g: 'Courts', id: 'sjc', name: 'Supreme Judicial Court', does: 'Writes the court rules. Its decisions apply to all towns.', makes: ['court', 'case'] },
    { g: 'Publishers and vendors', id: 'icc', name: 'International Code Council', key: true, does: 'A private nonprofit organization, not a government agency. It writes model codes: complete building rules that a government can adopt, such as the IRC, IBC, IEBC, IECC and IMC. Officials, builders and engineers help write them, and a new edition comes every 3 years. The ICC holds the copyright: the codes are free to read online, but copies and search cost money. Maine adopts the 2021 editions by rule. The ICC also owns General Code (eCode360).', makes: ['model'] },
    { g: 'Publishers and vendors', id: 'gc', name: 'General Code (eCode360)', does: 'Shows the official City Code online. Owned by the ICC since 2017. Its terms limit copies.', makes: [], hosts: ['ord', 'attach', 'newlaw', 'charter'] },
    { g: 'Publishers and vendors', id: 'nfpa', name: 'NFPA', does: 'Writes NFPA 101 (Life Safety Code) and NFPA 70 (National Electrical Code).', makes: ['std'] },
    { g: 'Publishers and vendors', id: 'other', name: 'IAPMO, ASHRAE, ASTM', does: 'Plumbing code, ventilation and energy standards, test standards such as E1465 radon.', makes: ['std'] },
    { g: 'Federal', id: 'fema', name: 'FEMA', does: 'Flood maps and the National Flood Insurance Program. The basis for Ch. 145. The inspector is Floodplain Administrator.', makes: [], hosts: ['ord'] },
    { g: 'Assistant', id: 'team', name: 'Assistant team', does: 'Writes short staff notes. The inspector reviews them.', makes: ['notes'] }
  ];

  var STEPS = [
    { lane: 'Permit', id: 's1', name: 'Questions', what: 'People call or visit. Do I need a permit? What can I build? How far from the line? Applications are PDF forms. There is no online portal.', src: [['ord', 'Ch. 275 zoning tables, Ch. 127'], ['forms', 'Permit applications']], who: ['ceo'], tool: 'Public answers with permit checklists, permit guide, fee estimate' },
    { lane: 'Permit', id: 's2', name: 'Plan review', what: 'Check zone, setbacks, lot coverage and site plan. Find the approvals that must come first.', src: [['model', 'MUBEC and ICC codes'], ['std', 'NFPA 101'], ['ord', 'Ch. 275, 145, 161, 244'], ['rules', 'Shoreland, septic rules']], who: ['ceo', 'pb', 'fire', 'ep', 'sfm', 'dep'], tool: 'Project approvals checklist, research desk' },
    { lane: 'Permit', id: 's3', name: 'Permit and fee', what: 'Issue and sign the permit. Work without a permit pays double, maximum $500, then $1,000 after 30 days.', src: [['ord', '§ 127-3'], ['attach', 'Fee schedules'], ['forms', 'Fees on the form']], who: ['ceo', 'ep'], tool: 'Fee estimate from published fees only', time: '§ 127-3B: 30 days' },
    { lane: 'Permit', id: 's4', name: 'Inspections', field: true, what: 'Minimum three: foundation, framing before cover, final. A missed inspection call can cost $100 per day.', src: [['model', 'ICC codes, from memory or the viewer'], ['std', 'Standards']], who: ['ceo', 'ep'], tool: 'Offline reading of saved sections. The tool cannot inspect.', time: 'Permit void if work does not start in 6 months' },
    { lane: 'Permit', id: 's5', name: 'Occupancy', what: 'Issue the certificate of occupancy when the building meets MUBEC and the Life Safety Code. Keep records for the life of the building.', src: [['ord', '§§ 127-5, 127-6'], ['std', 'NFPA 101']], who: ['ceo', 'fire'], tool: 'Case notebook for the property' },
    { lane: 'Complaint', id: 'c1', name: 'Complaint', field: true, what: 'Poor maintenance, unregistered vehicles, unsafe buildings. The resident makes an appointment and completes a paper form. The inspector visits.', src: [['ord', 'Ch. 205, § 210-10'], ['stat', '17 M.R.S. dangerous buildings']], who: ['ceo', 'fire'], tool: 'Printable complaint sheet, case notebook' },
    { lane: 'Complaint', id: 'c2', name: 'Notice of violation', what: 'A written order: section, facts, correction, deadline, appeal right, penalty range. For Ch. 205, a copy goes to the mortgage holder.', src: [['ord', '§ 205-7, § 275-6.1'], ['stat', '30-A M.R.S. §§ 2691, 4452'], ['manual', 'Legal Issues Manual']], who: ['ceo', 'sol'], tool: 'Notice drafter with Word export, deadline calculator' },
    { lane: 'Complaint', id: 'c3', name: 'Agreement or court', what: 'Sign a consent agreement, or file a Rule 80K citation in District Court. Find the owner in the registry of deeds. Attach a certified copy of the ordinance.', src: [['court', 'M.R. Civ. P. 80K'], ['stat', '§ 4452(3) penalty levels'], ['manual', '80K Manual']], who: ['ceo', 'council', 'sol', 'dc'], tool: 'Court citation packet checklist' },
    { lane: 'Appeal', id: 'a1', name: 'Zoning Appeals', what: 'Any inspector decision can be appealed within 30 days. The board decides again on the full facts. The inspector takes the $25 fee, sets the hearing within 45 days and mails notice to owners within 300 feet, 14 days before.', src: [['ord', '§ 275-6.2'], ['stat', '30-A M.R.S. § 2691']], who: ['bza', 'ceo'], tool: 'Deadline calculator', time: '30 days to appeal, hearing within 45 days' },
    { lane: 'Appeal', id: 'a2', name: 'Superior Court', what: 'A board decision can be appealed to Superior Court.', src: [['court', 'M.R. Civ. P. 80B'], ['case', 'Court decisions']], who: ['sc', 'sol'], tool: 'Deadline calculator' }
  ];

  var docById = {}, entById = {};
  DOCS.forEach(function (d) { docById[d.id] = d; });
  ENTS.forEach(function (e) { entById[e.id] = e; });

  function el(tag, cls, html) { var n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  // ---------------------------------------------------------------- map
  var colEnt = document.getElementById('col-ent'), colDoc = document.getElementById('col-doc');
  var detail = document.getElementById('detail'), svg = document.getElementById('wires'), grid = document.getElementById('mapgrid');
  var btns = {};
  var groups = {};
  ENTS.forEach(function (e) {
    if (!groups[e.g]) { groups[e.g] = el('div', 'grp'); groups[e.g].appendChild(el('div', 'label', esc(e.g))); colEnt.appendChild(groups[e.g]); }
    var b = el('button', 'pick', '<span class="nm' + (e.key ? ' key' : '') + '">' + esc(e.name) + '</span>');
    b.type = 'button'; b.dataset.id = e.id; groups[e.g].appendChild(b); btns[e.id] = b;
  });
  var dg = el('div', 'grp'); dg.appendChild(el('div', 'label', 'Types of documents')); colDoc.appendChild(dg);
  DOCS.forEach(function (d) {
    var b = el('button', 'pick', '<i class="sw ' + d.force + '" title="' + FORCE[d.force] + '"></i><span class="nm">' + esc(d.name) + '</span><i class="cov ' + d.cov + '" title="' + COV[d.cov] + '"></i>');
    b.type = 'button'; b.dataset.id = d.id; dg.appendChild(b); btns[d.id] = b;
  });

  var EDGES = [];
  ENTS.forEach(function (e) {
    (e.makes || []).forEach(function (d) { EDGES.push({ a: e.id, b: d, dash: false }); });
    (e.hosts || []).forEach(function (d) { EDGES.push({ a: e.id, b: d, dash: true }); });
  });

  function draw() {
    var box = grid.getBoundingClientRect();
    svg.setAttribute('viewBox', '0 0 ' + box.width + ' ' + box.height);
    svg.innerHTML = '';
    if (getComputedStyle(svg).display === 'none') return;
    EDGES.forEach(function (ed) {
      var A = btns[ed.a].getBoundingClientRect(), B = btns[ed.b].getBoundingClientRect();
      var x1 = A.right - box.left, y1 = A.top + A.height / 2 - box.top;
      var x2 = B.left - box.left, y2 = B.top + B.height / 2 - box.top;
      var mx = (x1 + x2) / 2;
      var p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      p.setAttribute('d', 'M' + x1 + ' ' + y1 + ' C' + mx + ' ' + y1 + ' ' + mx + ' ' + y2 + ' ' + x2 + ' ' + y2);
      p.dataset.a = ed.a; p.dataset.b = ed.b;
      if (ed.dash) p.classList.add('dash');
      svg.appendChild(p);
    });
    mark();
  }

  var current = 'icc';
  function related(id) {
    var r = {};
    EDGES.forEach(function (ed) { if (ed.a === id) r[ed.b] = 1; if (ed.b === id) r[ed.a] = 1; });
    return r;
  }
  function mark() {
    var r = related(current);
    Object.keys(btns).forEach(function (k) {
      var b = btns[k];
      b.classList.toggle('on', k === current);
      b.classList.toggle('rel', !!r[k]);
      b.classList.toggle('dim', k !== current && !r[k]);
      b.setAttribute('aria-pressed', String(k === current));
    });
    svg.querySelectorAll('path').forEach(function (p) {
      var hi = p.dataset.a === current || p.dataset.b === current;
      p.classList.toggle('hi', hi);
      if (hi) svg.appendChild(p);
    });
  }
  function usedIn(docId) { return STEPS.filter(function (s) { return s.src.some(function (x) { return x[0] === docId; }); }); }
  function stepsFor(entId) { return STEPS.filter(function (s) { return s.who.indexOf(entId) >= 0; }); }
  function stepTags(list) { return list.length ? '<span class="tags">' + list.map(function (s) { return '<span class="tag">' + esc(s.name) + '</span>'; }).join('') + '</span>' : 'Not a direct part of the workflow'; }

  function show(id) {
    current = id;
    var d = docById[id], e = entById[id], h = '';
    if (d) {
      var makers = EDGES.filter(function (x) { return x.b === id && !x.dash; }).map(function (x) { return entById[x.a].name; });
      var hosts = EDGES.filter(function (x) { return x.b === id && x.dash; }).map(function (x) { return entById[x.a].name; });
      h += '<div class="kind">Type of document</div><h3>' + esc(d.name) + '</h3><p>' + esc(d.covers) + '</p><dl>';
      h += '<dt>Legal force</dt><dd><span class="tag"><i class="sw ' + d.force + '"></i>' + FORCE[d.force] + '</span></dd>';
      h += '<dt>Example</dt><dd><code>' + esc(d.eg) + '</code></dd>';
      h += '<dt>Made by</dt><dd>' + esc(makers.join(', ') || 'None') + '</dd>';
      if (hosts.length) h += '<dt>Related</dt><dd>' + esc(hosts.join(', ')) + '</dd>';
      h += '<dt>Assistant</dt><dd><span class="tag"><i class="cov ' + d.cov + '"></i>' + COV[d.cov] + '</span></dd>';
      h += '<dt>Used in</dt><dd>' + stepTags(usedIn(id)) + '</dd></dl>';
    } else if (e) {
      h += '<div class="kind">' + esc(e.g) + '</div><h3>' + esc(e.name) + '</h3><p>' + esc(e.does) + '</p><dl>';
      h += '<dt>Makes</dt><dd>' + ((e.makes || []).length ? '<span class="tags">' + e.makes.map(function (m) { return '<span class="tag"><i class="sw ' + docById[m].force + '"></i>' + esc(docById[m].name) + '</span>'; }).join('') + '</span>' : 'No documents') + '</dd>';
      if (e.decides) h += '<dt>Decides</dt><dd>' + esc(e.decides) + '</dd>';
      if (e.hosts) h += '<dt>Related</dt><dd>' + esc(e.hosts.map(function (m) { return docById[m].name; }).join(', ')) + '</dd>';
      h += '<dt>Workflow</dt><dd>' + stepTags(stepsFor(id)) + '</dd></dl>';
    }
    detail.innerHTML = h;
    mark();
  }
  Object.keys(btns).forEach(function (k) { btns[k].addEventListener('click', function () { show(k); }); });

  // ---------------------------------------------------------------- lanes
  var lanes = document.getElementById('lanes'), sd = document.getElementById('stepdetail');
  var stepBtns = {};
  ['Permit', 'Complaint', 'Appeal'].forEach(function (name) {
    var lane = el('div', 'lane');
    lane.appendChild(el('div', 'label', name === 'Appeal' ? 'Appeal<br><span style="text-transform:none;letter-spacing:0;font-weight:400">from any decision</span>' : name));
    var track = el('div', 'track');
    var list = STEPS.filter(function (s) { return s.lane === name; });
    list.forEach(function (s, i) {
      if (i) track.appendChild(el('span', 'conn'));
      var forces = s.src.map(function (x) { return docById[x[0]].force; });
      var b = el('button', 'stepbtn' + (s.field ? ' field' : ''),
        '<span class="n">' + (STEPS.indexOf(s) + 1) + '</span><span class="t">' + esc(s.name) + '</span><span class="dots">' + forces.map(function (f) { return '<i class="sw ' + f + '"></i>'; }).join('') + '</span>');
      b.type = 'button'; b.dataset.id = s.id;
      b.addEventListener('click', function () { pickStep(s.id); });
      stepBtns[s.id] = b; track.appendChild(b);
    });
    lane.appendChild(track); lanes.appendChild(lane);
  });
  function pickStep(id) {
    var s = STEPS.filter(function (x) { return x.id === id; })[0];
    Object.keys(stepBtns).forEach(function (k) { stepBtns[k].classList.toggle('on', k === id); stepBtns[k].setAttribute('aria-pressed', String(k === id)); });
    sd.innerHTML =
      '<div><div class="label">' + esc(s.lane) + (s.field ? ', field work' : '') + '</div><h3>' + esc(s.name) + '</h3><p>' + esc(s.what) + '</p>' + (s.time ? '<div class="time">Clock: ' + esc(s.time) + '</div>' : '') + '</div>' +
      '<div><div class="label">Sources</div><ul>' + s.src.map(function (x) { var d = docById[x[0]]; return '<li><i class="sw ' + d.force + '"></i><span><b>' + esc(d.name) + ':</b> ' + esc(x[1]) + '</span></li>'; }).join('') + '</ul></div>' +
      '<div><div class="label">Who is involved</div><div class="tags" style="margin-top:6px">' + s.who.map(function (w) { return '<span class="tag">' + esc(entById[w].name) + '</span>'; }).join('') + '</div><div class="tool">Preview tool: ' + esc(s.tool) + '</div></div>';
  }

  show('icc');
  pickStep('s1');
  draw();
  window.addEventListener('resize', function () { requestAnimationFrame(draw); });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(draw);
  if (window.ResizeObserver) new ResizeObserver(function () { requestAnimationFrame(draw); }).observe(grid);
})();

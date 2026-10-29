import { useState } from 'react';
import { ArrowDownToLine, ArrowRight, ArrowUpRight, ChartNoAxesCombined, Check, Route } from 'lucide-react';
import data from '../public/results/data.json';
import { Globe } from './Globe';
import './results.css';

const entries = [
  { id: 'static', label: 'Static', color: '#777786' },
  { id: 'reactive', label: 'Adaptive', color: '#8b8bfe' },
  { id: 'predictive-trend', label: 'Predictive · trend', color: '#7fd579' },
  { id: 'predictive-learned', label: 'Predictive · learned', color: '#d896ff' },
] as const;
const pct = (n: number) => `${(n * 100).toFixed(2)}%`;
const pp = (n: number) => `${n >= 0 ? '+' : ''}${(n * 100).toFixed(2)}`;
const benchmark = data.benchmark;
const extended = data.extended;
const stats = extended.statistics;
// Version asset URLs by measured content so browsers never show stale charts after regeneration.
// generated_at changes exactly when any published measurement changes.
const asset = (name: string) => `/results/${name}?v=${encodeURIComponent(data.generated_at)}`;
const adaptive = data.live.runs.reactive;
type PolicyId = typeof entries[number]['id'];
const labelOf = (id: string) => entries.find(e => e.id === id)?.label ?? id;
const bestId = entries.reduce<PolicyId>((a, e) => stats.by_policy[e.id].mean > stats.by_policy[a].mean ? e.id : a, 'static');
const best = stats.by_policy[bestId];
const compare = (candidate: string, baseline: string) => stats.comparisons.find(c => c.candidate === candidate && c.baseline === baseline);
const verdict = (c: (typeof stats.comparisons)[number]) => c.conclusion === 'higher' ? 'delivered more than' : c.conclusion === 'lower' ? 'delivered less than' : 'was not distinguishable from';
const ciText = (ci: number[]) => `95% CI ${pp(ci[0])} to ${pp(ci[1])} pp`;
const predictionHelps = ['predictive-trend', 'predictive-learned'].some(id => compare(id, 'reactive')?.conclusion === 'higher');
const learnedVsTrend = compare('predictive-learned', 'predictive-trend');

function RouteReplay() {
  const events = [...adaptive.events].sort((a, b) => a.time_s - b.time_s);
  const [selected, setSelected] = useState(1);
  const event = events[selected];
  const beta = event.new_route.includes('sb:fwd');
  const failed = event.time_s >= 16 && event.time_s < 20;
  return <div className="route-replay">
    <div className="replay-heading"><span>ADAPTIVE ROUTE REPLAY</span><span>RECORDED DECISIONS</span></div>
    <svg viewBox="0 0 600 190" role="img" aria-label={`At ${event.time_s} seconds: Source to ${beta ? 'Beta' : 'Alpha'} to Destination${failed ? '; Beta link is down' : ''}`}>
      <g fill="none" strokeWidth="2">
        <path d="M80 100L300 42L520 100" stroke={beta ? '#3a3a46' : '#8b8bfe'}/>
        <path d="M80 100L300 158" stroke={failed ? '#d896aa' : beta ? '#8b8bfe' : '#3a3a46'} strokeDasharray={failed ? '5 5' : undefined}/>
        <path d="M300 158L520 100" stroke={beta ? '#8b8bfe' : '#3a3a46'}/>
      </g>
      <g className="replay-wire-label"><text x="190" y="47">1 Mbps · 2 ms</text><text x="410" y="47">1 Mbps · 2 ms</text><text x="190" y="154">{failed ? 'LINK DOWN' : '2.5 Mbps · 12 ms'}</text><text x="410" y="154">2.5 Mbps · 12 ms</text></g>
      {[[80,100,'Source'],[300,42,'Alpha'],[300,158,'Beta'],[520,100,'Destination']].map(([x,y,name])=><g key={name}>
        <circle cx={x} cy={y} r="21" fill="#161616" stroke={name === (beta?'Beta':'Alpha') ? '#8b8bfe' : '#5a5a6c'}/>
        <path d={`M${Number(x)-8} ${y}h16m-4-4 4 4-4 4m-8-8-4 4 4 4`} fill="none" stroke="#aaaacb" strokeWidth="1.5"/>
        <text x={x} y={Number(y)+36} className="replay-node-label">{name}</text>
      </g>)}
    </svg>
    <div className="replay-controls" aria-label="Recorded routing events">{events.map((e,i)=><button key={e.time_s} aria-pressed={selected===i} onClick={()=>setSelected(i)}><span>{e.time_s.toFixed(1)}s</span>{['Initial path','Traffic rerouted','Link failover','Path restored'][i]}</button>)}</div>
    <p className="replay-caption"><span className="tiny-square"/>Source → {beta?'Beta':'Alpha'} → Destination <span>{event.reason.replaceAll('_',' ')}</span></p>
  </div>;
}

export function Results() {
  const [metric,setMetric] = useState<'delivery'|'latency'>('delivery');
  const gain = compare(bestId, 'static');
  return <div className="results-page">
    <header className="app-header results-header">
      <a className="brand" href="#studio" aria-label="SmartRoute studio"><span className="brand-mark"><Route size={21}/></span>smartroute<span className="brand-dot">®</span></a>
      <div className="header-separator"/><nav className="header-nav"><a href="#studio">Network studio</a><a href="#results" className="active" aria-current="page"><span className="tiny-square"/>Results</a></nav>
      <a className="results-return" href="#studio">Open the studio <ArrowUpRight size={15}/></a>
    </header>
    <main className="results-main">
      <section className="results-hero">
        <div><div className="eyebrow"><span/>MEASURED IN THE NETWORK</div><h1>Better paths.<br/><span>Measured outcomes.</span></h1><p>What happens when traffic grows and a link goes down?<br className="desktop-break"/> Explore the simulator’s results, from individual reroutes to a paired benchmark.</p><div className="results-hero-tags"><span><Check size={12}/>{extended.runs.toLocaleString()} audited runs</span><span>{extended.seeds} held-out seeds</span><span>Experiment {data.experiment_version}</span><span>Simulated traffic</span></div></div>
        <div className="results-globe"><Globe/><span>OBSERVE / COMPARE / UNDERSTAND</span></div>
      </section>

      <section className="results-kpis" aria-label="Benchmark highlights">
        <div><span>BEST MEAN DELIVERY</span><strong>{pct(best.mean)}</strong><small>{labelOf(bestId)} · 95% CI {pct(best.ci95[0])}–{pct(best.ci95[1])}</small></div>
        <div><span>GAIN OVER STATIC</span><strong>{gain ? pp(gain.mean_delta) : '—'}<em>pp</em></strong><small>{gain ? ciText(gain.ci95) : 'No paired static comparison'}</small></div>
        <div><span>PAIRED WORKLOADS</span><strong>{extended.families}<em>families</em></strong><small>Identical traces for every policy</small></div>
        <div><span>BENCHMARK FAILURES</span><strong>{String(extended.failed).padStart(2, '0')}<em>/ {extended.runs.toLocaleString()}</em></strong><small>All runs completed and audited</small></div>
      </section>

      <section className="results-section" aria-labelledby="comparison-title">
        <div className="results-section-heading"><div><span className="results-index">01 / POLICY COMPARISON</span><h2 id="comparison-title">Four approaches. The same traffic.</h2><p>Mean outcomes across {(extended.runs / 5).toLocaleString()} runs per policy on {extended.seeds} fresh seeds ({extended.seed_range[0]}–{extended.seed_range[1]}) that the model never saw. Higher delivery and lower latency are better.</p></div><a className="results-download" href={asset('benchmark.csv')} download><ArrowDownToLine size={14}/>Run-level CSV</a></div>
        <div className="results-comparison">
          <figure className="result-figure"><div className="figure-top"><span>{metric==='delivery'?'PACKETS SUCCESSFULLY DELIVERED':'MEAN LATENCY OF DELIVERED PACKETS'}</span><div className="metric-tabs" aria-label="Chart metric"><button aria-pressed={metric==='delivery'} onClick={()=>setMetric('delivery')}>Delivery</button><button aria-pressed={metric==='latency'} onClick={()=>setMetric('latency')}>Latency</button></div></div><img src={asset(`${metric}.svg`)} alt={metric==='delivery'?`Delivery: ${entries.map(e=>`${e.label} ${pct(extended.report[e.id].delivery_ratio)}`).join(', ')}.`:`Mean latency: ${entries.map(e=>`${e.label} ${(extended.report[e.id].mean_latency_s*1000).toFixed(2)} ms`).join(', ')}.`}/><figcaption>Unweighted means of run-level metrics; not pooled packet ratios.{metric==='delivery'?' Whiskers: paired seed-block bootstrap 95% intervals.':''} <a href={asset(`${metric}.svg`)} download>Download graph ↗</a></figcaption></figure>
          <aside className="results-insight"><ChartNoAxesCombined size={23}/><span className="results-index">WHAT THE TESTS SHOW</span><h3>{predictionHelps ? 'Prediction helps.' : 'Adaptation helps.'}<br/>{learnedVsTrend?.conclusion === 'lower' ? 'Simple trend beats the learned model.' : learnedVsTrend?.conclusion === 'higher' ? 'The learned model leads.' : 'Learned and trend are tied.'}</h3><ul className="results-verdicts">{stats.comparisons.map(c=><li key={c.candidate+c.baseline} data-conclusion={c.conclusion}>{labelOf(c.candidate)} {verdict(c)} {labelOf(c.baseline)}: <b>{pp(c.mean_delta)} pp</b> <span>{ciText(c.ci95)}</span></li>)}</ul><p className="results-small">Paired by seed: every policy saw identical packets. These results describe this simulator’s workloads, not physical equipment.</p></aside>
        </div>
        <figure className="result-figure"><div className="figure-top"><span>PAIRED DIFFERENCES IN DELIVERY · 95% INTERVALS</span></div><img src={asset('paired.svg')} alt={stats.comparisons.map(c=>`${labelOf(c.candidate)} vs ${labelOf(c.baseline)}: ${pp(c.mean_delta)} percentage points, ${ciText(c.ci95)}.`).join(' ')}/><figcaption>Each line is a candidate-minus-baseline delivery difference averaged over {stats.cells_per_block} topology/scenario runs per seed, resampled over {stats.seed_blocks} seed blocks ({stats.draws.toLocaleString()} draws). An interval that does not cross zero is a clear difference. <a href={asset('paired.svg')} download>Download graph ↗</a></figcaption></figure>
        <div className="results-table-wrap"><table className="results-table"><caption>Measured benchmark outcomes by routing policy</caption><thead><tr><th scope="col">Routing policy</th><th scope="col">Delivery ↑</th><th scope="col">95% CI</th><th scope="col">Mean latency ↓</th><th scope="col">Goodput ↑</th><th scope="col">Route changes / run</th></tr></thead><tbody>{entries.map(({id,label,color})=>{const m=extended.report[id];const ci=stats.by_policy[id].ci95;return <tr key={id}><th scope="row"><i style={{background:color}}/>{label}</th><td>{pct(m.delivery_ratio)}</td><td>{pct(ci[0])}–{pct(ci[1])}</td><td>{(m.mean_latency_s*1000).toFixed(2)} ms</td><td>{(m.throughput_bps/1e6).toFixed(3)} Mbps</td><td>{m.route_changes.toFixed(2)}</td></tr>;})}</tbody></table></div>
        <details className="results-details"><summary>See packet delivery by traffic scenario <span>07 SCENARIOS +</span></summary><div className="results-table-wrap"><table className="results-table"><caption>Delivery by scenario, averaged over two topologies and {extended.seeds} seeds</caption><thead><tr><th scope="col">Scenario</th>{entries.map(e=><th key={e.id} scope="col">{e.label}</th>)}</tr></thead><tbody>{Object.entries(extended.by_scenario).map(([scenario,values])=><tr key={scenario}><th scope="row" className="scenario-name">{scenario}</th>{entries.map(e=><td key={e.id}>{pct(values[e.id])}</td>)}</tr>)}</tbody></table></div></details>
        <details className="results-details"><summary>Compare with the original sealed test <span>{benchmark.runs} RUNS +</span></summary><div className="results-table-wrap"><table className="results-table"><caption>Mean delivery: original v{data.experiment_version} sealed test (5 seeds) and the larger held-out test ({extended.seeds} seeds)</caption><thead><tr><th scope="col">Routing policy</th><th scope="col">Original · {benchmark.runs} runs</th><th scope="col">Held-out · {extended.runs.toLocaleString()} runs</th></tr></thead><tbody>{entries.map(({id,label,color})=><tr key={id}><th scope="row"><i style={{background:color}}/>{label}</th><td>{pct(benchmark.report[id].delivery_ratio)}</td><td>{pct(extended.report[id].delivery_ratio)}</td></tr>)}</tbody></table></div></details>
      </section>

      <section className="results-section" aria-labelledby="live-title">
        <div className="results-section-heading"><div><span className="results-index">02 / A FRESH LIVE EXPERIMENT</span><h2 id="live-title">Turn up traffic. Then break a link.</h2><p>A separate 24-second run using the same live engine as the studio.</p></div><span className="results-label">4 POLICIES · 0.2s STEPS</span></div>
        <figure className="result-figure trace-figure"><img src={asset('traffic.svg')} alt="During a 24-second run, traffic increases from 0.35 to 1.8 Mbps at 8 seconds. Beta fails at 16 seconds and returns at 20 seconds. Adaptive cumulative goodput exceeds static routing."/><figcaption>Goodput is cumulative from session start; it responds gradually. Pending packets remain pending at 24s. <a href={asset('traffic.svg')} download>Download graph ↗</a></figcaption></figure>
        <div className="results-replay-grid"><RouteReplay/><div className="live-outcome"><span className="results-index">SAME DEMAND. DIFFERENT OUTCOME.</span><h3>{adaptive.metrics.delivered.toLocaleString()}<span> packets delivered</span></h3><p>Adaptive routing delivered { (adaptive.metrics.delivered-data.live.runs.static.metrics.delivered).toLocaleString()} more packets than static in this example, with {adaptive.metrics.route_changes} route changes.</p><div className="live-counts"><span><b>{adaptive.metrics.dropped}</b>dropped</span><span><b>{adaptive.metrics.pending}</b>pending</span><span><b>{adaptive.metrics.forced_route_changes}</b>forced repair</span></div><p className="results-small">Both policies generated {adaptive.metrics.generated.toLocaleString()} packets. Trend and learned matched adaptive in this particular run. Click a recorded event to inspect its path.</p></div></div>
      </section>

      <section className="results-section studio-capture" aria-labelledby="capture-title"><div className="results-section-heading"><div><span className="results-index">03 / INSIDE THE STUDIO</span><h2 id="capture-title">The decisions stay visible.</h2><p>Edit capacity, follow packets, and inspect why a route changed.</p></div><a className="results-download" href="#studio">Try your own network <ArrowRight size={15}/></a></div><figure className="result-figure"><a href={asset('studio.jpg')} target="_blank" rel="noreferrer" aria-label="Open full-size studio screenshot"><img src={asset('studio.jpg')} loading="lazy" alt="SmartRoute React studio with six network devices, editable cable capacity, traffic controls, and a rerouting event log."/></a><figcaption>Actual studio capture from a separate interactive verification run. <a href={asset('studio.jpg')} download>Download image ↗</a></figcaption></figure></section>

      <section className="results-method"><div><span className="results-index">HOW TO READ THESE RESULTS</span><h2>Measured, with clear limits.</h2></div><div><p>The headline benchmark covers 7 scenarios × 2 topologies × {extended.seeds} seeds × 5 policies = {extended.runs.toLocaleString()} runs on seeds {extended.seed_range[0]}–{extended.seed_range[1]}, disjoint from every training, validation and original test family. Each seed sets one of five load levels, so every level appears {extended.seeds / 5} times. Four policies appear above; the fifth is a persistence baseline that matches adaptive routing. The original {benchmark.runs}-run sealed test is kept for comparison.</p><p>Intervals come from a paired percentile bootstrap that resamples whole seeds ({stats.draws.toLocaleString()} draws, fixed RNG seed), never individual packets.</p><p>Latency covers delivered packets only; read it alongside delivery and drops. Benchmark runs have no pending packets. The separate live example uses a growing packet cohort with no final drain. These are simulated networks, not measurements from physical Cisco equipment.</p><p>The learned forecaster is a locally trained Ridge model: 25,760 simulated training examples and 7,728 validation examples. It forecasts demand; the shared controller chooses routes. It does not learn during a session.</p><div className="results-source-links"><a href={asset('data.json')} download><ArrowDownToLine size={13}/>All page data</a><a href={asset('audit.json')} download><ArrowDownToLine size={13}/>Audit record</a><a href={asset('statistics.json')} download><ArrowDownToLine size={13}/>Intervals</a><a href={asset('benchmark-v1.3.csv')} download><ArrowDownToLine size={13}/>Original 350-run CSV</a></div></div></section>
      <footer className="results-footer"><span>SMARTROUTE / RESULTS · v{data.experiment_version}</span><span>Live example generated {new Date(data.generated_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})}</span><a href="#studio">Build your next network <ArrowUpRight size={13}/></a></footer>
    </main>
  </div>;
}

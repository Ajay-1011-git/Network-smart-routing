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
const benchmark = data.benchmark;
const adaptive = data.live.runs.reactive;
const best = benchmark.report['predictive-trend'];

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
  const improvement = (best.delivery_ratio - benchmark.report.static.delivery_ratio) * 100;
  return <div className="results-page">
    <header className="app-header results-header">
      <a className="brand" href="#studio" aria-label="SmartRoute studio"><span className="brand-mark"><Route size={21}/></span>smartroute<span className="brand-dot">®</span></a>
      <div className="header-separator"/><nav className="header-nav"><a href="#studio">Network studio</a><a href="#results" className="active" aria-current="page"><span className="tiny-square"/>Results</a></nav>
      <a className="results-return" href="#studio">Open the studio <ArrowUpRight size={15}/></a>
    </header>
    <main className="results-main">
      <section className="results-hero">
        <div><div className="eyebrow"><span/>MEASURED IN THE NETWORK</div><h1>Better paths.<br/><span>Measured outcomes.</span></h1><p>What happens when traffic grows and a link goes down?<br className="desktop-break"/> Explore the simulator’s results, from individual reroutes to a paired benchmark.</p><div className="results-hero-tags"><span><Check size={12}/>350 audited runs</span><span>Experiment {data.experiment_version}</span><span>Simulated traffic</span></div></div>
        <div className="results-globe"><Globe/><span>OBSERVE / COMPARE / UNDERSTAND</span></div>
      </section>

      <section className="results-kpis" aria-label="Benchmark highlights">
        <div><span>BEST MEAN DELIVERY</span><strong>{pct(best.delivery_ratio)}</strong><small>Predictive · trend</small></div>
        <div><span>GAIN OVER STATIC</span><strong>+{improvement.toFixed(2)}<em>pp</em></strong><small>Percentage points in delivery</small></div>
        <div><span>PAIRED WORKLOADS</span><strong>{benchmark.families}<em>families</em></strong><small>Identical traces for every policy</small></div>
        <div><span>BENCHMARK FAILURES</span><strong>00<em>/ {benchmark.runs}</em></strong><small>All runs completed and audited</small></div>
      </section>

      <section className="results-section" aria-labelledby="comparison-title">
        <div className="results-section-heading"><div><span className="results-index">01 / POLICY COMPARISON</span><h2 id="comparison-title">Four approaches. The same traffic.</h2><p>Mean outcomes across 70 runs per policy. Higher delivery and lower latency are better.</p></div><a className="results-download" href="/results/benchmark.csv" download><ArrowDownToLine size={14}/>Run-level CSV</a></div>
        <div className="results-comparison">
          <figure className="result-figure"><div className="figure-top"><span>{metric==='delivery'?'PACKETS SUCCESSFULLY DELIVERED':'MEAN LATENCY OF DELIVERED PACKETS'}</span><div className="metric-tabs" aria-label="Chart metric"><button aria-pressed={metric==='delivery'} onClick={()=>setMetric('delivery')}>Delivery</button><button aria-pressed={metric==='latency'} onClick={()=>setMetric('latency')}>Latency</button></div></div><img src={`/results/${metric}.svg`} alt={metric==='delivery'?'Delivery: Static 84.42%, Adaptive 90.14%, Trend 92.43%, Learned 91.38%.':'Mean latency: Static 79.52 ms, Adaptive 61.79 ms, Trend 58.34 ms, Learned 58.14 ms.'}/><figcaption>Unweighted means of run-level metrics; not pooled packet ratios. <a href={`/results/${metric}.svg`} download>Download graph ↗</a></figcaption></figure>
          <aside className="results-insight"><ChartNoAxesCombined size={23}/><span className="results-index">WHAT THE TESTS SHOW</span><h3>Prediction helps.<br/>The method still matters.</h3><p>The trend policy delivered the most packets overall. The learned model also improved on adaptive routing, but did not win every comparison.</p><div><b>{pct(benchmark.report['predictive-learned'].delivery_ratio)}</b><span>Learned model delivery</span></div><p className="results-small">These results describe this simulator’s workloads. A trained model is not automatically the best routing policy.</p></aside>
        </div>
        <div className="results-table-wrap"><table className="results-table"><caption>Measured benchmark outcomes by routing policy</caption><thead><tr><th scope="col">Routing policy</th><th scope="col">Delivery ↑</th><th scope="col">Mean latency ↓</th><th scope="col">Goodput ↑</th><th scope="col">Route changes / run</th></tr></thead><tbody>{entries.map(({id,label,color})=>{const m=benchmark.report[id];return <tr key={id}><th scope="row"><i style={{background:color}}/>{label}</th><td>{pct(m.delivery_ratio)}</td><td>{(m.mean_latency_s*1000).toFixed(2)} ms</td><td>{(m.throughput_bps/1e6).toFixed(3)} Mbps</td><td>{m.route_changes.toFixed(2)}</td></tr>;})}</tbody></table></div>
        <details className="results-details"><summary>See packet delivery by traffic scenario <span>07 SCENARIOS +</span></summary><div className="results-table-wrap"><table className="results-table"><caption>Delivery by scenario, averaged over two topologies and five seeds</caption><thead><tr><th scope="col">Scenario</th>{entries.map(e=><th key={e.id} scope="col">{e.label}</th>)}</tr></thead><tbody>{Object.entries(benchmark.by_scenario).map(([scenario,values])=><tr key={scenario}><th scope="row" className="scenario-name">{scenario}</th>{entries.map(e=><td key={e.id}>{pct(values[e.id])}</td>)}</tr>)}</tbody></table></div></details>
      </section>

      <section className="results-section" aria-labelledby="live-title">
        <div className="results-section-heading"><div><span className="results-index">02 / A FRESH LIVE EXPERIMENT</span><h2 id="live-title">Turn up traffic. Then break a link.</h2><p>A separate 24-second run using the same live engine as the studio.</p></div><span className="results-label">4 POLICIES · 0.2s STEPS</span></div>
        <figure className="result-figure trace-figure"><img src="/results/traffic.svg" alt="During a 24-second run, traffic increases from 0.35 to 1.8 Mbps at 8 seconds. Beta fails at 16 seconds and returns at 20 seconds. Adaptive cumulative goodput exceeds static routing."/><figcaption>Goodput is cumulative from session start; it responds gradually. Pending packets remain pending at 24s. <a href="/results/traffic.svg" download>Download graph ↗</a></figcaption></figure>
        <div className="results-replay-grid"><RouteReplay/><div className="live-outcome"><span className="results-index">SAME DEMAND. DIFFERENT OUTCOME.</span><h3>{adaptive.metrics.delivered.toLocaleString()}<span> packets delivered</span></h3><p>Adaptive routing delivered { (adaptive.metrics.delivered-data.live.runs.static.metrics.delivered).toLocaleString()} more packets than static in this example, with {adaptive.metrics.route_changes} route changes.</p><div className="live-counts"><span><b>{adaptive.metrics.dropped}</b>dropped</span><span><b>{adaptive.metrics.pending}</b>pending</span><span><b>{adaptive.metrics.forced_route_changes}</b>forced repair</span></div><p className="results-small">Both policies generated {adaptive.metrics.generated.toLocaleString()} packets. Trend and learned matched adaptive in this particular run. Click a recorded event to inspect its path.</p></div></div>
      </section>

      <section className="results-section studio-capture" aria-labelledby="capture-title"><div className="results-section-heading"><div><span className="results-index">03 / INSIDE THE STUDIO</span><h2 id="capture-title">The decisions stay visible.</h2><p>Edit capacity, follow packets, and inspect why a route changed.</p></div><a className="results-download" href="#studio">Try your own network <ArrowRight size={15}/></a></div><figure className="result-figure"><a href="/results/studio.jpg" target="_blank" rel="noreferrer" aria-label="Open full-size studio screenshot"><img src="/results/studio.jpg" loading="lazy" alt="SmartRoute React studio with six network devices, editable cable capacity, traffic controls, and a rerouting event log."/></a><figcaption>Actual studio capture from a separate interactive verification run. <a href="/results/studio.jpg" download>Download image ↗</a></figcaption></figure></section>

      <section className="results-method"><div><span className="results-index">HOW TO READ THESE RESULTS</span><h2>Measured, with clear limits.</h2></div><div><p>The benchmark covers 7 scenarios × 2 topologies × 5 seeds × 5 policies = 350 runs. Four policies appear above; the fifth is a persistence baseline that matches adaptive routing. Traffic traces are paired and training, validation, and test families are disjoint.</p><p>Latency covers delivered packets only; read it alongside delivery and drops. Benchmark runs have no pending packets. The separate live example uses a growing packet cohort with no final drain. These are simulated networks, not measurements from physical Cisco equipment.</p><p>The learned forecaster is a locally trained Ridge model: 25,760 simulated training examples and 7,728 validation examples. It forecasts demand; the shared controller chooses routes. It does not learn during a session.</p><div className="results-source-links"><a href="/results/data.json" download><ArrowDownToLine size={13}/>All page data</a><a href="/results/audit.json" download><ArrowDownToLine size={13}/>Audit record</a></div></div></section>
      <footer className="results-footer"><span>SMARTROUTE / RESULTS · v{data.experiment_version}</span><span>Live example generated {new Date(data.generated_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'})}</span><a href="#studio">Build your next network <ArrowUpRight size={13}/></a></footer>
    </main>
  </div>;
}

/* Stage 1 reports: all data comes from SPECIAL-protected backend endpoints. */
(() => {
  const panel = document.getElementById("analytics-panel");
  if (!panel) return;
  let report = null;
  let version = 0;
  let worldPromise;
  const number = value => Number(value || 0).toLocaleString();
  const duration = value => `${(Number(value || 0)/60).toLocaleString(undefined, { maximumFractionDigits: 1 })} min`;
  const names = new Intl.DisplayNames(["en"], { type: "region" });
  const countryName = code => code === "XX" ? "Unknown" : (names.of(code) || code);
  const make = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const start = document.getElementById("analytics-start");
  const end = document.getElementById("analytics-end");
  const country = document.getElementById("analytics-country");
  const feedback = document.getElementById("analytics-status");
  const metric = document.getElementById("analytics-metric");
  const utcDate = date => date.toISOString().slice(0, 10);
  const today = new Date();
  end.value = utcDate(today); end.max = start.max = utcDate(today);
  start.value = utcDate(new Date(today.getTime()-6*86400000));
  start.min = end.min = utcDate(new Date(today.getTime()-89*86400000));

  function params() {
    const value = new URLSearchParams({ start: start.value, end: end.value });
    if (country.value) value.set("country", country.value);
    return value;
  }

  function table(target, columns, rows) {
    const host = document.getElementById(target);
    host.replaceChildren();
    if (!rows?.length) { host.append(make("p", "No activity recorded for this selection.", "analytics-empty")); return; }
    const wrapper = make("div", undefined, "analytics-table-scroll");
    const table = make("table");
    const head = make("tr");
    for (const [label] of columns) { const cell = make("th", label); cell.scope = "col"; head.append(cell); }
    const thead = make("thead"); thead.append(head); table.append(thead);
    const tbody = make("tbody");
    for (const row of rows) {
      const tr = make("tr");
      for (const [, format] of columns) tr.append(make("td", format(row)));
      tbody.append(tr);
    }
    table.append(tbody); wrapper.append(table); host.append(wrapper);
  }

  function chart(target, rows, key, label) {
    const host = document.getElementById(target); host.replaceChildren();
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 900 260"); svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `${label}; exact values are available in the data table below.`);
    const max = Math.max(1, ...rows.map(row => Number(row[key] || 0)));
    const point = (row, i) => [58+i*818/Math.max(1,rows.length-1), 215-Number(row[key] || 0)/max*175];
    for (let i=0; i<=4; i++) {
      const y=215-i*175/4;
      const line = document.createElementNS(ns,"line");
      for (const [attr,value] of Object.entries({x1:58,x2:876,y1:y,y2:y,stroke:"#bba9bd25"})) line.setAttribute(attr,value);
      svg.append(line);
      const text = document.createElementNS(ns,"text"); text.setAttribute("x", "3"); text.setAttribute("y", y+4);
      text.textContent = number(Math.round(max*i/4)); svg.append(text);
    }
    const path = document.createElementNS(ns,"polyline");
    path.setAttribute("points", rows.map((row,i)=>point(row,i).join(",")).join(" "));
    path.setAttribute("fill","none"); path.setAttribute("stroke","#c99ae5"); path.setAttribute("stroke-width","3"); svg.append(path);
    rows.forEach((row,i) => {
      const [x,y] = point(row,i); const circle = document.createElementNS(ns,"circle");
      circle.setAttribute("cx",x); circle.setAttribute("cy",y); circle.setAttribute("r","4"); circle.setAttribute("fill","#c9a66b");
      const title = document.createElementNS(ns,"title"); title.textContent = `${row.date ?? `${row.hour}:00 UTC`}: ${number(row[key])}`;
      circle.append(title); svg.append(circle);
      if (i === 0 || i === rows.length-1 || (rows.length <= 10)) {
        const text = document.createElementNS(ns,"text"); text.setAttribute("x", x); text.setAttribute("y","244");
        text.setAttribute("text-anchor",i===0?"start":i===rows.length-1?"end":"middle");
        text.textContent = row.date?.slice(5) ?? `${row.hour}:00`; svg.append(text);
      }
    });
    host.append(svg);
  }

  function render() {
    const data = report.report;
    const totals = data.totals;
    const cards = document.getElementById("analytics-cards"); cards.replaceChildren();
    const average = totals.engaged_sessions ? totals.active_seconds/totals.engaged_sessions : 0;
    for (const [label,value] of [["Page views",number(totals.page_views)],["Visits started",number(totals.visits)],
      ["Anonymous visits",number(totals.anonymous_visits)],["Signed-in accounts",number(totals.signed_in_accounts)],
      ["Frontend requests",number(totals.frontend_requests)],["Backend requests",number(totals.backend_requests)],
      ["Active time",duration(totals.active_seconds)],["Average per engaged session",duration(average)],
      ["New accounts",totals.signups === null ? "All countries only" : number(totals.signups)]]) {
      const card = make("div",undefined,"analytics-card"); card.append(make("span",label),make("strong",value)); cards.append(card);
    }
    const previous = data.previous;
    document.getElementById("analytics-comparison").textContent = `Previous equal period: ${number(previous.page_views)} page views · ${number(previous.requests)} requests · ${duration(previous.active_seconds)} active time. Previous data may be unavailable before collection began or beyond 90-day retention.`;
    drawDaily();
    const hours = Array.from({length:24},(_,hour)=>({hour,requests:0,page_views:0,...data.hourly.find(row=>row.hour===hour)}));
    chart("analytics-hour-chart",hours,"requests","Requests by hour of day, combined across the selected UTC dates");
    table("analytics-hour-table",[["Hour (UTC)",r=>`${r.hour}:00`],["Requests",r=>number(r.requests)],["Page views",r=>number(r.page_views)]],hours);
    const selected = country.value;
    if (!selected) {
      country.replaceChildren(new Option("All countries", ""));
      data.countries.forEach(row=>country.add(new Option(countryName(row.country),row.country)));
    }
    table("analytics-countries",[["Country",r=>countryName(r.country)],["Page views",r=>number(r.page_views)],
      ["Requests",r=>number(r.requests)],["Engaged sessions",r=>number(r.engaged_sessions)],
      ["Active time",r=>duration(r.active_seconds)],["Average active time",r=>duration(r.engaged_sessions?r.active_seconds/r.engaged_sessions:0)]],data.countries);
    void drawMap();
    const bars = document.getElementById("analytics-country-bars"); bars.replaceChildren();
    const max = Math.max(1,...data.countries.map(row=>row.page_views));
    data.countries.slice(0,12).forEach(row=>{
      const line = make("div",undefined,"analytics-country-bar"); const bar=make("span");
      bar.style.width=`${row.page_views/max*100}%`;
      line.append(make("span",`${countryName(row.country)} · ${number(row.page_views)} views`),bar); bars.append(line);
    });
    table("analytics-pages",[["Page",r=>r.path],["Views",r=>number(r.page_views)],["Entrances",r=>number(r.entrances)],["Last page in visit",r=>number(r.last_pages)]],data.pages);
    table("analytics-types",[["Source",r=>r.source],["Type",r=>r.kind],["Requests",r=>number(r.requests)]],data.request_types);
    table("analytics-accounts",[["Account",r=>r.username],["Sessions",r=>number(r.sessions)],["Views",r=>number(r.page_views)],["Active time",r=>duration(r.active_seconds)]],data.accounts);
    const health=report.collection;
    document.getElementById("analytics-health").textContent = `Collection ${health.enabled?"enabled":"disabled"} · Edge trust ${health.edge_configured?"configured":"not configured"} · IP logging ${health.ip_logging?"enabled":"disabled"} · Latest stored event: ${data.latest_event || "none"} · This backend process: ${number(health.queued)} queued, ${number(health.dropped)} dropped, ${number(health.write_failures)} failed batches. Counts can lag by a few seconds.`;
  }

  async function drawMap() {
    const host=document.getElementById("analytics-map");
    const data=report?.report;
    if(!data) return;
    try {
      worldPromise ||= fetch("/assets/analytics-world.json").then(response=>{
        if(!response.ok) throw new Error("Map unavailable");
        return response.json();
      });
      const world=await worldPromise;
      if(data!==report?.report) return;
      const key=document.getElementById("analytics-map-metric").value;
      const max=Math.max(1,...data.countries.map(row=>Number(row[key] || 0)));
      const ns="http://www.w3.org/2000/svg";
      const svg=document.createElementNS(ns,"svg");
      svg.setAttribute("viewBox","0 0 900 390");svg.setAttribute("role","group");svg.setAttribute("aria-label","Country activity map. Use the country selector or table for all locations.");
      for(const shape of world.countries) {
        const row=data.countries.find(row=>row.country===shape.code);
        const value=Number(row?.[key] || 0);
        const path=document.createElementNS(ns,"path");path.setAttribute("d",shape.path);
        path.setAttribute("fill",value?`hsl(275 50% ${25+value/max*42}%)`:"#302237");
        const text=`${countryName(shape.code)}: ${key==="active_seconds"?duration(value):number(value)}`;
        const title=document.createElementNS(ns,"title");title.textContent=text;path.append(title);
        if(value>0) {
          path.setAttribute("tabindex","0");path.setAttribute("role","button");path.setAttribute("aria-label",`${text}. Filter by this country.`);
          const choose=()=>{country.value=shape.code;void load();};
          path.addEventListener("click",choose);
          path.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();choose();}});
        }
        svg.append(path);
      }
      host.replaceChildren(svg);
    } catch { worldPromise=null;host.replaceChildren(make("p","Map unavailable. Country totals remain available below.","analytics-note")); }
  }

  function drawDaily() {
    if (!report) return;
    chart("analytics-daily-chart",report.report.daily,metric.value,metric.selectedOptions[0].textContent);
    table("analytics-daily-table",[["Date (UTC)",r=>r.date],["Views",r=>number(r.page_views)],["Visits",r=>number(r.visits)],
      ["Frontend requests",r=>number(r.frontend_requests)],["Backend requests",r=>number(r.backend_requests)],
      ["Active time",r=>duration(r.active_seconds)],["Signups",r=>r.signups===null?"—":number(r.signups)]],report.report.daily);
  }

  async function load() {
    const current=++version;
    if (start.value>end.value) { feedback.textContent="Start date must come before the end date."; return; }
    feedback.textContent="Loading analytics…";
    document.getElementById("analytics-results").hidden=true;
    document.getElementById("analytics-export").disabled=true;
    try {
      const response=await authFetch(`${API_BASE}/api/admin/analytics?${params()}`);
      const data=await response.json(); if (!response.ok) throw new Error(data.detail || "Analytics could not be loaded.");
      if (current!==version) return;
      report=data; render(); feedback.textContent="";
      document.getElementById("analytics-results").hidden=false;
      document.getElementById("analytics-export").disabled=false;
    } catch(error) { if(current===version) feedback.textContent=error.message; }
  }
  document.getElementById("analytics-tab").addEventListener("click",()=>{
    for (const name of ["users","novels","definition","home","deletion","analytics"]) {
      document.getElementById(`${name}-panel`).hidden=name!=="analytics";
      document.getElementById(`${name}-tab`).setAttribute("aria-pressed",String(name==="analytics"));
    }
    document.getElementById("vote-workspace").hidden=true;
    void load();
  });
  document.getElementById("analytics-filters").addEventListener("submit",event=>{event.preventDefault();void load();});
  metric.addEventListener("change",drawDaily);
  document.getElementById("analytics-map-metric").addEventListener("change",()=>void drawMap());
  document.getElementById("analytics-export").addEventListener("click",async()=>{
    try {
      const response=await authFetch(`${API_BASE}/api/admin/analytics/export?${params()}`);
      if(!response.ok) throw new Error("Export failed. Refresh your report and try again.");
      const url=URL.createObjectURL(await response.blob()); const link=make("a"); link.href=url;link.download="axiom-analytics.csv";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    } catch(error) {feedback.textContent=error.message;}
  });
  let ipPage=1;
  async function loadIPs() {
    const host=document.getElementById("analytics-ip-status"); host.textContent="Loading restricted records…";
    try {
      const response=await authFetch(`${API_BASE}/api/admin/analytics/ip-logs?page=${ipPage}`);
      const data=await response.json(); if(!response.ok) throw new Error(data.detail || "IP logs unavailable.");
      table("analytics-ips",[["Time (UTC)",r=>r.occurred_at],["IP address",r=>r.ip]],data.rows);
      host.textContent=`Page ${ipPage} · Last seven days only. Access is logged.`;
      document.getElementById("analytics-ip-prev").disabled=ipPage===1;
      document.getElementById("analytics-ip-next").disabled=data.rows.length<50;
    } catch(error) {host.textContent=error.message;}
  }
  document.getElementById("analytics-ip-open").addEventListener("click",()=>{ipPage=1;void loadIPs();});
  document.getElementById("analytics-ip-prev").addEventListener("click",()=>{ipPage=Math.max(1,ipPage-1);void loadIPs();});
  document.getElementById("analytics-ip-next").addEventListener("click",()=>{ipPage++;void loadIPs();});
})();

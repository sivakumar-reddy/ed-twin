// Auto-derived from the validated standalone explorer. Scoped under .edtwin to avoid leaking into the host page.
export const ED_STYLES = `@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;450;500;600&display=swap');

  :root{
    --bg:#0A1316; --panel:#0F1B1F; --panel2:#0C171A; --line:#1C2F35; --line2:#15252A;
    --ink:#DCEAE7; --ink2:#A7BDBA; --muted:#6E8A8E; --faint:#476268;
    --stable:#34D399; --congested:#F5B945; --unstable:#F26D6D; --accent:#5EEAD4;
    --glow-amber:rgba(245,185,69,.5); --glow-red:rgba(242,109,109,.55);
  }
  *{box-sizing:border-box; margin:0; padding:0}
  .edtwin{background:var(--bg); color:var(--ink); font-family:'Inter',system-ui,sans-serif; -webkit-font-smoothing:antialiased; overflow:hidden; height:100%}
  .wrap{height:100vh; display:flex; flex-direction:column; max-width:1360px; margin:0 auto; padding:16px 22px 12px}

  /* Header */
  header{display:flex; align-items:center; justify-content:space-between; gap:18px; padding-bottom:9px; border-bottom:1px solid var(--line2)}
  .title-block{display:flex; flex-direction:column; gap:2px}
  .title{font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:16px; letter-spacing:-.01em; color:var(--ink)}
  .title b{color:var(--accent); font-weight:700}
  .thesis{font-family:'Inter',sans-serif; font-weight:450; font-size:11.5px; color:var(--muted)}
  .thesis em{color:var(--ink2); font-style:normal; font-weight:600}
  .chips{display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; max-width:560px}
  .chip{font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:.03em; color:var(--muted); background:var(--panel2); border:none; border-radius:5px; padding:4px 8px; white-space:nowrap}
  .chip b{color:var(--accent); font-weight:600}
  .chip .pulse{display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--stable); margin-right:5px; animation:pulse 2.4s ease-in-out infinite; vertical-align:middle}
  @keyframes pulse{0%,100%{opacity:.45} 50%{opacity:1}}

  /* Main grid */
  main{flex:1; display:grid; grid-template-columns:182px 1fr 176px; gap:14px; padding-top:14px; min-height:0}
  .col{display:flex; flex-direction:column; gap:10px; min-height:0}

  /* Lever tabs */
  .levers{display:flex; flex-wrap:wrap; gap:5px}
  .lever{font-family:'JetBrains Mono',monospace; font-size:10.5px; letter-spacing:.01em; padding:6px 9px; border:1px solid var(--line2); border-radius:6px; background:transparent; color:var(--muted); cursor:pointer; transition:all .15s}
  .lever:hover{border-color:var(--faint); color:var(--ink)}
  .lever.on{background:var(--accent); border-color:var(--accent); color:#04211C; font-weight:600}

  .card{background:var(--panel); border:none; border-radius:12px; padding:12px 14px}
  .ctl .row{display:flex; align-items:baseline; justify-content:space-between; margin-bottom:8px}
  .ctl-label{font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:13px}
  .ctl-val{font-family:'JetBrains Mono',monospace; font-size:13px; color:var(--accent); font-weight:600}
  input[type=range]{width:100%; -webkit-appearance:none; appearance:none; height:4px; border-radius:3px; background:var(--line); outline:none}
  input[type=range]::-webkit-slider-thumb{-webkit-appearance:none; width:15px; height:15px; border-radius:50%; background:var(--accent); cursor:pointer; border:3px solid var(--bg); box-shadow:0 0 0 1px var(--accent)}
  input[type=range]::-moz-range-thumb{width:13px; height:13px; border-radius:50%; background:var(--accent); cursor:pointer; border:3px solid var(--bg)}
  .ctl-foot{display:flex; justify-content:space-between; font-family:'JetBrains Mono',monospace; font-size:9.5px; color:var(--faint); margin-top:6px}

  /* Patient flow */
  .flow-title,.util-title,.cmp-title{font-family:'JetBrains Mono',monospace; font-size:9px; color:var(--faint); text-transform:uppercase; letter-spacing:.09em; margin-bottom:10px}
  .flow{flex:1; display:flex; flex-direction:column; min-height:0}
  .stages{display:flex; flex-direction:column; gap:0; flex:1; justify-content:space-between}
  .stage{display:flex; align-items:center; gap:9px; position:relative}
  .node{width:9px; height:9px; border-radius:50%; background:var(--faint); flex:none; transition:all .3s; position:relative; z-index:1}
  .stage .lbl{font-family:'JetBrains Mono',monospace; font-size:10.5px; color:var(--ink2); transition:color .3s}
  .stage .q{font-family:'JetBrains Mono',monospace; font-size:9px; color:var(--faint); margin-left:auto; opacity:0; transition:opacity .3s}
  .stage.warm .node{background:var(--congested)}
  .stage.warm .lbl{color:var(--ink)}
  .stage.hot .node{background:var(--unstable)}
  .stage.hot .lbl{color:var(--ink)}
  .stage.bottleneck .node{box-shadow:0 0 0 4px var(--glow-amber); animation:bnpulse 1.8s ease-in-out infinite}
  .stage.hot.bottleneck .node{box-shadow:0 0 0 4px var(--glow-red)}
  .stage.show-q .q{opacity:1}
  @keyframes bnpulse{0%,100%{box-shadow:0 0 0 3px var(--glow-amber)} 50%{box-shadow:0 0 0 6px rgba(245,185,69,.15)}}
  /* dynamic flow: spine, queues, focal bottleneck, upstream propagation */
  .stages{position:relative}
  .stages::before{content:''; position:absolute; left:4px; top:7px; bottom:7px; width:1.5px; background:var(--line2); border-radius:2px}
  .qdots{display:inline-flex; gap:3px; align-items:center; margin-left:9px; height:9px}
  .qdots i{width:4px; height:4px; border-radius:50%; background:var(--congested); display:inline-block; animation:qpop .35s ease both, qbreath 2.1s ease-in-out infinite}
  .qdots.red i{background:var(--unstable)}
  @keyframes qpop{from{transform:scale(0); opacity:0} to{transform:scale(1); opacity:.9}}
  @keyframes qbreath{0%,100%{opacity:.9} 50%{opacity:.45}}
  .stage.focal .lbl{font-weight:600; color:var(--ink); transform:scale(1.05); transform-origin:left center}
  .stage.backedup .lbl{color:var(--congested)}
  .stages.severe .stage.backedup .lbl{color:var(--unstable)}
  .flow.focusing .stage:not(.focal):not(.backedup):not(.bottleneck){opacity:.5}
  .stage{transition:opacity .4s ease}
  .stage .lbl{transition:color .3s, transform .3s ease}
  .spine-pulse{position:absolute; left:.5px; top:0; width:8px; height:24px; border-radius:6px; opacity:0; pointer-events:none; filter:blur(.5px);
    background:linear-gradient(to top, rgba(245,185,69,0), rgba(245,185,69,.42), rgba(245,185,69,0))}
  .stages.propagate .spine-pulse{opacity:1; animation:propup 2.4s ease-in-out infinite}
  .stages.propagate.severe .spine-pulse{background:linear-gradient(to top, rgba(242,109,109,0), rgba(242,109,109,.46), rgba(242,109,109,0))}
  @keyframes propup{0%{transform:translateY(var(--p-from,180px)); opacity:0} 18%{opacity:1} 82%{opacity:1} 100%{transform:translateY(var(--p-to,40px)); opacity:0}}
  /* reset button */
  .reset-btn{margin-top:9px; width:100%; font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); background:transparent; border:1px solid var(--line2); border-radius:6px; padding:6px 0; cursor:pointer; transition:all .15s}
  .reset-btn::before{content:'↺'; margin-right:6px; font-size:10px}
  .reset-btn:hover:not(:disabled){color:var(--accent); border-color:rgba(94,234,212,.4)}
  .reset-btn:disabled{opacity:.34; cursor:default}
  /* footer */
  .appfoot{font-family:'JetBrains Mono',monospace; font-size:9px; color:var(--faint); letter-spacing:.04em; text-align:center; padding:10px 0 2px; margin-top:6px; border-top:1px solid var(--line2)}
  .appfoot b{color:var(--muted); font-weight:600}
  .connector{width:1px; height:11px; background:var(--line); margin-left:4px}
  .connector.flowing{background:linear-gradient(var(--accent),transparent); animation:flowdash 1.2s linear infinite}

  /* Center chart */
  .chart-card{background:var(--panel); border:none; border-radius:14px; padding:18px 26px 12px; display:flex; flex-direction:column; min-height:0; flex:1; box-shadow:0 10px 38px rgba(0,0,0,0.30)}
  .chart-head{display:flex; align-items:flex-start; justify-content:space-between; gap:10px; margin-bottom:8px}
  .chart-titles{display:flex; flex-direction:column; gap:3px}
  .chart-title{font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:22px; letter-spacing:-.01em; line-height:1.05}
  .chart-sub{font-family:'JetBrains Mono',monospace; font-size:12.5px; color:var(--muted); letter-spacing:.02em}
  .head-right{display:flex; align-items:center; gap:10px}
  .threshold-pill{font-family:'JetBrains Mono',monospace; font-size:11px; padding:5px 11px; border-radius:20px; letter-spacing:.02em; transition:all .3s; border:1px solid transparent}
  .metric-toggle{display:flex; gap:5px}
  .mbtn{font-family:'JetBrains Mono',monospace; font-size:11px; padding:6px 11px; border:1px solid var(--line2); border-radius:6px; background:transparent; color:var(--muted); cursor:pointer; transition:all .15s}
  .mbtn:hover{color:var(--ink); border-color:var(--faint)}
  .mbtn.on{background:var(--line); color:var(--ink); border-color:var(--faint)}
  svg{width:100%; flex:1; min-height:0; display:block}
  .explain{font-family:'Inter',sans-serif; font-size:11.5px; line-height:1.5; color:var(--ink2); padding:8px 2px 0; border-top:1px solid var(--line2); margin-top:9px; min-height:36px}
  .explain b{color:var(--ink); font-weight:600}
  .explain .tag{font-family:'JetBrains Mono',monospace; font-size:9px; text-transform:uppercase; letter-spacing:.08em; color:var(--faint); display:inline; margin-right:7px}

  /* Right rail */
  .status{display:flex; align-items:center; gap:8px; margin-bottom:12px}
  .dot{width:9px; height:9px; border-radius:50%}
  .status-txt{font-family:'JetBrains Mono',monospace; font-size:12px; font-weight:600; letter-spacing:.05em; text-transform:uppercase}
  .cause{font-family:'JetBrains Mono',monospace; font-size:9.5px; color:var(--muted); margin-left:auto; letter-spacing:.01em; text-align:right}
  .bignum{display:flex; align-items:baseline; gap:7px}
  .bignum .v{font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:30px; line-height:1; letter-spacing:-.02em; font-variant-numeric:tabular-nums}
  .bignum .u{font-family:'JetBrains Mono',monospace; font-size:10.5px; color:var(--muted)}
  .bignum .ci{font-family:'JetBrains Mono',monospace; font-size:9.5px; color:var(--faint)}
  .bignum-label{font-family:'JetBrains Mono',monospace; font-size:8.5px; color:var(--faint); text-transform:uppercase; letter-spacing:.07em; margin:2px 0 9px}
  .verdict{font-family:'Inter',sans-serif; font-size:11px; font-weight:500; line-height:1.4; margin:-5px 0 11px; min-height:15px; transition:color .35s ease}
  .read{font-family:'Inter',sans-serif; font-size:11.5px; line-height:1.52; color:var(--ink2); margin-top:6px}
  .read b{color:var(--ink); font-weight:600}
  .subs{display:grid; grid-template-columns:1fr 1fr; gap:7px; margin-bottom:10px}
  .sub{background:var(--panel2); border:none; border-radius:8px; padding:6px 9px}
  .sub .sv{font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:15px; font-variant-numeric:tabular-nums}
  .sub .sl{font-family:'JetBrains Mono',monospace; font-size:8px; color:var(--faint); text-transform:uppercase; letter-spacing:.03em; margin-top:1px}

  .meter{margin-bottom:6px}
  .meter .mrow{display:flex; justify-content:space-between; font-family:'JetBrains Mono',monospace; font-size:10px; margin-bottom:3px}
  .meter .mname{color:var(--muted)} .meter .mval{color:var(--ink); font-variant-numeric:tabular-nums}
  .track{height:5px; border-radius:3px; background:var(--line); position:relative; overflow:hidden}
  .fill{height:100%; border-radius:3px; transition:width .35s cubic-bezier(.4,0,.2,1), background .35s}
  .track .redline{position:absolute; top:-2px; bottom:-2px; width:1.5px; background:var(--unstable); opacity:.6}

  /* Comparison */
  .cmp{display:flex; flex-direction:column; gap:8px}
  .cmp-row{display:grid; grid-template-columns:1fr auto; align-items:center; gap:8px}
  .cmp-name{font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--muted)}
  .cmp-vals{display:flex; align-items:baseline; gap:6px; font-family:'JetBrains Mono',monospace; font-size:11px; font-variant-numeric:tabular-nums}
  .cmp-base{color:var(--faint)}
  .cmp-arrow{color:var(--faint); font-size:9px}
  .cmp-cur{font-weight:600}
  .sim-stat{margin-top:auto; padding-top:11px; border-top:1px solid var(--line2)}
  .sim-stat .ssv{font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:16px; color:var(--ink); font-variant-numeric:tabular-nums}
  .sim-stat .ssl{font-family:'JetBrains Mono',monospace; font-size:9px; color:var(--faint); text-transform:uppercase; letter-spacing:.05em; margin-top:2px; line-height:1.5}

  .ax{font-family:'JetBrains Mono',monospace; font-size:11px; fill:var(--faint)}
  .axlabel{font-family:'JetBrains Mono',monospace; font-size:11px; fill:var(--faint); letter-spacing:.03em}
  .zonelabel{font-family:'JetBrains Mono',monospace; font-size:13px; letter-spacing:.02em; font-weight:500}
  .draw{stroke-dasharray:1; stroke-dashoffset:1; animation:draw .7s ease-out forwards}
  @keyframes draw{to{stroke-dashoffset:0}}
  .fadein{animation:fade .5s ease-out}
  @keyframes fade{from{opacity:0} to{opacity:1}}
  #opgroup,#opvert{transition:transform .32s cubic-bezier(.4,0,.2,1)}
  #opdot,#ophalo,#opline{transition:fill .25s ease, stroke .25s ease}
  #opbg{transition:width .2s ease, x .2s ease}
  .opval{font-family:'JetBrains Mono',monospace; font-weight:600; font-size:12px}
  .anno{transition:opacity .45s ease, transform .45s cubic-bezier(.2,.7,.2,1)}

  /* guided tour */
  .header-right{display:flex; align-items:center; gap:16px}
  .tour-launch{font-family:'JetBrains Mono',monospace; font-size:10.5px; letter-spacing:.04em; color:var(--accent); background:rgba(94,234,212,.07); border:1px solid rgba(94,234,212,.28); border-radius:7px; padding:7px 13px; cursor:pointer; white-space:nowrap; transition:all .18s ease}
  .tour-launch:hover{background:rgba(94,234,212,.14); border-color:rgba(94,234,212,.5)}
  .tour-launch::before{content:'▶'; font-size:8px; margin-right:7px; position:relative; top:-1px}
  .tour-scrim{position:fixed; inset:0; background:rgba(5,11,13,.66); backdrop-filter:blur(2px); -webkit-backdrop-filter:blur(2px); opacity:0; pointer-events:none; transition:opacity .45s ease; z-index:50}
  .edtwin.touring .tour-scrim{opacity:1; pointer-events:auto}
  .edtwin.touring .chart-card{position:relative; z-index:60; box-shadow:0 0 0 1px rgba(94,234,212,.22), 0 24px 80px rgba(0,0,0,.55)}
  .edtwin.touring #rightCard{position:relative; z-index:60; box-shadow:0 0 0 1px rgba(94,234,212,.14), 0 24px 80px rgba(0,0,0,.5)}
  .edtwin.touring #levers,.edtwin.touring .ctl,.edtwin.touring .flow{filter:saturate(.6) brightness(.92); transition:filter .4s ease}
  .tour-panel{position:fixed; left:50%; bottom:24px; transform:translateX(-50%) translateY(14px); width:min(700px,93vw); background:linear-gradient(180deg,#102025,#0C181C); border:1px solid var(--line); border-radius:15px; padding:18px 22px 16px; z-index:70; opacity:0; pointer-events:none; transition:opacity .45s ease, transform .5s cubic-bezier(.2,.7,.2,1); box-shadow:0 24px 80px rgba(0,0,0,.6)}
  .edtwin.touring .tour-panel{opacity:1; pointer-events:auto; transform:translateX(-50%) translateY(0)}
  .tour-step{font-family:'JetBrains Mono',monospace; font-size:9.5px; letter-spacing:.16em; text-transform:uppercase; color:var(--accent)}
  .tour-title{font-family:'Space Grotesk',sans-serif; font-weight:600; font-size:16.5px; letter-spacing:-.01em; color:var(--ink); margin-top:7px}
  .tour-body{font-family:'Inter',sans-serif; font-size:12.5px; line-height:1.58; color:var(--ink2); margin-top:9px; min-height:62px; transition:opacity .3s ease}
  .tour-body b{color:var(--ink); font-weight:600}
  .tour-body .pos{color:var(--stable); font-weight:600}
  .tour-body .neg{color:var(--unstable); font-weight:600}
  .tour-body .warn{color:var(--congested); font-weight:600}
  .tour-foot{display:flex; align-items:center; justify-content:space-between; margin-top:15px; gap:14px}
  .tour-dots{display:flex; gap:7px}
  .tour-dot{width:6px; height:6px; border-radius:50%; background:var(--line); transition:background .3s ease, transform .3s ease}
  .tour-dot.on{background:var(--accent); transform:scale(1.25)}
  .tour-dot.done{background:rgba(94,234,212,.4)}
  .tour-btns{display:flex; gap:8px}
  .tbtn{font-family:'JetBrains Mono',monospace; font-size:11px; padding:7px 15px; border-radius:7px; border:1px solid var(--line2); background:transparent; color:var(--muted); cursor:pointer; transition:all .15s ease}
  .tbtn:hover{color:var(--ink2); border-color:var(--muted)}
  .tbtn.primary{background:var(--accent); color:#06241F; border-color:transparent; font-weight:600}
  .tbtn.primary:hover{background:#7af0dd; color:#06241F}
  .tbtn.ghost{border-color:transparent; color:var(--faint)}
  .tbtn.ghost:hover{color:var(--muted)}
  .tbtn:disabled{opacity:.32; cursor:default; color:var(--faint)}

  /* ============================================================
     RESPONSIVE: phones (portrait + landscape) and small tablets.
     Desktop layout above is untouched. Fixes: right panel clipped
     in portrait, chart vanishing in landscape, bottom cut off.
     ============================================================ */
  @media (max-width: 900px){
    /* make the app the vertical scroll container instead of clipping */
    .edtwin{height:100%; overflow-x:hidden; overflow-y:auto; -webkit-overflow-scrolling:touch;}
    .wrap{height:auto; min-height:100%; max-width:100%; padding:14px 14px 20px;}

    /* header stacks so chips don't push off-screen */
    header{flex-direction:column; align-items:flex-start; gap:12px;}
    .header-right{flex-direction:column-reverse; align-items:flex-start; gap:12px; width:100%;}
    .chips{justify-content:flex-start; max-width:100%;}

    /* the key fix: three columns become one full-width stack */
    main{display:grid; grid-template-columns:1fr; gap:16px; height:auto; flex:none; padding-top:16px;}
    .col{min-height:0;}

    /* lift the payoff up: chart first, then the STABLE/length-of-stay/utilization
       readout, then the levers + slider + patient-flow list last. matches the
       desktop "everything important first" feel and keeps the live numbers
       sitting right above the slider when you do scroll down to drag it. */
    main > .col:nth-child(2){order:1;}   /* chart */
    main > .col:nth-child(3){order:2;}   /* readout: status, 332, utilization */
    main > .col:nth-child(1){order:3;}   /* levers, slider, patient flow */

    /* chart can no longer collapse to zero: give it a real height */
    .chart-card{flex:none;}
    .chart-head{flex-wrap:wrap;}
    .chart-title{font-size:19px;}
    svg{height:300px; flex:none;}

    /* right rail and flow render at natural height, full width */
    #rightCard{flex:none !important;}
    .flow{flex:none;}
    .stages{flex:none; justify-content:flex-start; gap:13px;}
    .spine-pulse{display:none;}
  }

  /* very short landscape phones: slightly shorter chart so more fits */
  @media (max-width: 900px) and (max-height: 480px){
    svg{height:240px;}
  }

`;

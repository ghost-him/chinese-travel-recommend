/* app.js — 渲染与交互。数据全部来自 data.js（window.TRIP） */
(function () {
  "use strict";
  var T = window.TRIP;
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function imgSrc(id) {
    return "images/" + (/\.(jpe?g|png|webp|svg|avif)$/i.test(id) ? id : id + ".jpg");
  }
  function creditOf(id) { return T.credits[id] || { author: "Unknown", license: "", file: "" }; }

  /* ---------- 0. 头部元信息 ---------- */
  function renderMeta() {
    $("#meta-built").textContent = T.meta.builtAt;
    $("#meta-fare").textContent = T.meta.fareQueriedAt;
    $("#meta-ref").textContent = T.meta.fareRefDate;
    var fare2 = $("#meta-fare-2");
    if (fare2) fare2.textContent = T.meta.fareQueriedAt;
    $$("[data-trip-range]").forEach(function (n) {
      n.textContent = T.meta.tripStart.replace(/-/g, ".") + " – " + T.meta.tripEnd.replace(/-/g, ".");
    });
    $("#hero-title").textContent = T.meta.title;
    $("#hero-sub").textContent = T.meta.subtitle;
    var chips = $("#hero-chips");
    (T.meta.chips || [T.meta.tripDays + " 天", "推荐单位：地点群"]).forEach(function (t) {
      chips.appendChild(el("span", "chip", t));
    });

    var brand = $("#brand-text");
    if (brand) brand.textContent = T.meta.title;
    document.title = T.meta.title + "｜旅行推荐报告";
    if ($("#src-query")) $("#src-query").textContent = T.meta.fareQueriedAt || "—";
    if ($("#src-ref")) $("#src-ref").textContent = T.meta.fareRefDate || "—";
    if (T.meta.isTemplate) {
      var banner = el("div", "template-banner",
        "模板占位数据：替换 js/data.js 后，把 meta.isTemplate 改为 false 再对外分享。");
      document.body.insertBefore(banner, document.body.firstChild);
    }

    $("#presale-observed").textContent = T.meta.presale.observed;
    $("#presale-conclusion").textContent = T.meta.presale.conclusion;
    $("#presale-risk").textContent = T.meta.presale.risk;
  }

  /* ---------- 1. 画像字段清单 ---------- */
  function renderProfile() {
    var tb = $("#profile-fields tbody");
    T.profileFields.forEach(function (f) {
      var tr = el("tr");
      tr.appendChild(el("td", "f-label", f.label));
      var tdWhy = el("td", "f-why", f.why);
      tr.appendChild(tdWhy);
      tr.appendChild(el("td", "f-example", f.example));
      var tdReq = el("td");
      var b = el("span", "badge " + (f.required ? "badge-req" : "badge-opt"), f.required ? "必填" : "建议");
      tdReq.appendChild(b);
      tr.appendChild(tdReq);
      tb.appendChild(tr);
    });

    var s = T.sampleProfile;
    var dl = $("#profile-sample");
    [
      ["出发地", s.origin],
      ["同行者", s.companion],
      ["日期", s.dates],
      ["预算", s.budget],
      ["偏好", s.style]
    ].forEach(function (kv) {
      var wrap = el("div", "kv");
      wrap.appendChild(el("span", "k", kv[0]));
      wrap.appendChild(el("span", "v", kv[1]));
      dl.appendChild(wrap);
    });
  }

  /* ---------- 2. 评分矩阵 ---------- */
  var activePreset = T.presets[0];

  function scoreOf(dest, dims) {
    var sum = 0, wsum = 0;
    dims.forEach(function (d) {
      sum += (dest.s[d.key] || 0) * d.w;
      wsum += d.w;
    });
    return (sum / wsum / 5) * 100;
  }

  function fitInfo(c) {
    var d = T.meta.tripDays || 0;
    var lo = c.fit ? c.fit[0] : 0;
    var hi = c.fit ? c.fit[1] : 99;
    if (d < lo) return { ok: false, text: "需 ≥" + lo + " 天" };
    if (d > hi) return { ok: true, text: "时间富余" };
    return { ok: true, text: "天数匹配" };
  }

  function renderScore() {
    var dims = T.dims.map(function (d) {
      return { key: d.key, label: d.label, w: activePreset.w[d.key] != null ? activePreset.w[d.key] : d.w };
    });
    var rows = T.clusters.map(function (c) {
      return { d: c, score: scoreOf(c, dims), fit: fitInfo(c) };
    }).sort(function (a, b) {
      if (a.fit.ok !== b.fit.ok) return a.fit.ok ? -1 : 1;
      return b.score - a.score;
    });

    var table = $("#score-table");
    table.innerHTML = "";
    var thead = el("thead"), htr = el("tr");
    htr.appendChild(el("th", "th-name", "地点群"));
    dims.forEach(function (d) {
      var th = el("th", null, d.label);
      th.appendChild(el("span", "th-w", d.w + "%"));
      htr.appendChild(th);
    });
    htr.appendChild(el("th", "th-total", "加权分"));
    thead.appendChild(htr);
    table.appendChild(thead);

    var tbody = el("tbody");
    rows.forEach(function (r, i) {
      var tr = el("tr");
      if (i === 0) tr.className = "row-top";
      if (!r.fit.ok) tr.className = "row-fail";
      var tdName = el("td", "td-name");
      tdName.appendChild(el("strong", null, r.d.name));
      tdName.appendChild(el("span", "td-style", r.d.style));
      tdName.appendChild(el("span", "td-region", r.d.cities.join(" + ") + " · " + r.d.days));
      tr.appendChild(tdName);
      dims.forEach(function (dm) {
        var v = r.d.s[dm.key] || 0;
        var td = el("td", "td-score");
        var dots = el("span", "dots");
        td.appendChild(dots);
        for (var k = 0; k < 5; k++) {
          var dot = el("i", "dot" + (k < v ? " on" : ""));
          td.firstChild.appendChild(dot);
        }
        td.appendChild(el("span", "num", String(v)));
        tr.appendChild(td);
      });
      var tdTotal = el("td", "td-total");
      tdTotal.appendChild(el("strong", null, r.score.toFixed(0)));
      if (!r.fit.ok) {
        tdTotal.appendChild(el("span", "fit-bad", r.fit.text));
      } else if (i === 0) {
        tdTotal.appendChild(el("span", "pick", "首选"));
      }
      tr.appendChild(tdTotal);
      tbody.appendChild(tr);

      var trNote = el("tr", "row-note");
      var tdNote = el("td");
      tdNote.colSpan = dims.length + 2;
      tdNote.appendChild(el("span", "note-main", r.d.note));
      tdNote.appendChild(el("span", "note-link", "群内：" + r.d.link));
      trNote.appendChild(tdNote);
      tbody.appendChild(trNote);
    });
    table.appendChild(tbody);

    var sw = $("#preset-switch");
    sw.innerHTML = "";
    T.presets.forEach(function (p) {
      var b = el("button", "seg" + (p.id === activePreset.id ? " active" : ""), p.name);
      b.type = "button";
      b.addEventListener("click", function () {
        activePreset = p;
        renderScore();
        $("#score-hint").textContent = "已按「" + p.name.replace("（当前）", "") + "」权重重排；权重可在 data.js 的 presets 中改。";
      });
      sw.appendChild(b);
    });
  }

  /* ---------- 3. 方案详情 ---------- */
  var activePlan = Object.keys(T.plans)[0];

  function renderPlanTabs() {
    var nav = $("#plan-tabs");
    nav.innerHTML = "";
    Object.keys(T.plans).forEach(function (k) {
      var p = T.plans[k];
      var b = el("button", "tab" + (k === activePlan ? " active" : ""));
      b.type = "button";
      b.appendChild(el("span", "tab-name", p.name));
      b.appendChild(el("span", "tab-verdict", (p.clusterLabel ? p.clusterLabel + " · " : "") + p.verdict));
      b.addEventListener("click", function () { activePlan = k; renderPlanTabs(); renderPlan(); });
      nav.appendChild(b);
    });
  }

  function renderPlan() {
    var p = T.plans[activePlan];
    var root = $("#plan-body");
    root.innerHTML = "";
    var planTitle = $("#plan-title");
    if (planTitle) {
      planTitle.textContent = "推荐方案：" + p.name + (T.meta.tripDays ? " · " + T.meta.tripDays + " 天" : "");
    }

    /* 3.1 标题与理由 */
    var head = el("div", "plan-head");
    var headTxt = el("div", "plan-head-txt");
    headTxt.appendChild(el("p", "plan-kicker", (p.clusterLabel ? p.clusterLabel + " ｜ " : "") + p.tagline));
    headTxt.appendChild(el("h2", "plan-name", p.name));
    var whyList = el("ul", "why-list");
    p.why.forEach(function (t) { whyList.appendChild(el("li", null, t)); });
    headTxt.appendChild(whyList);
    head.appendChild(headTxt);

    var heroWrap = el("figure", "plan-hero");
    var heroImg = el("img");
    heroImg.src = imgSrc(p.hero);
    heroImg.alt = p.name + " 代表性景观";
    heroImg.loading = "lazy";
    heroWrap.appendChild(heroImg);
    var cred = creditOf(p.hero);
    heroWrap.appendChild(el("figcaption", null, "图：" + cred.author + " / " + cred.license + " / Wikimedia Commons"));
    head.appendChild(heroWrap);
    root.appendChild(head);

    /* 3.2 风土人情 */
    var customs = el("section", "block");
    customs.appendChild(el("h3", "block-title", "风土人情：先懂这几件事，再进城"));
    var cg = el("div", "customs-grid");
    p.customs.forEach(function (c) {
      var card = el("article", "custom");
      card.appendChild(el("h4", null, c.t));
      card.appendChild(el("p", null, c.d));
      cg.appendChild(card);
    });
    customs.appendChild(cg);
    root.appendChild(customs);

    /* 3.3 行程 */
    var days = el("section", "block");
    days.appendChild(el("h3", "block-title", "时间安排：" + p.days.length + " 天，按天给主线（可整体平移）"));
    var dayGrid = el("div", "day-grid");
    p.days.forEach(function (d) {
      var card = el("article", "day");
      var dh = el("header", "day-head");
      dh.appendChild(el("span", "day-n", "D" + d.n));
      dh.appendChild(el("span", "day-date", d.date));
      dh.appendChild(el("span", "day-theme", d.theme));
      card.appendChild(dh);
      var ul = el("ul", "timeline");
      d.items.forEach(function (it) {
        var li = el("li", "tl-item tl-" + it.kind);
        li.appendChild(el("span", "tl-time", it.time));
        var body = el("div", "tl-body");
        body.appendChild(el("p", "tl-what", it.what));
        body.appendChild(el("span", "tl-dur", it.dur));
        li.appendChild(body);
        ul.appendChild(li);
      });
      card.appendChild(ul);
      dayGrid.appendChild(card);
    });
    days.appendChild(dayGrid);
    root.appendChild(days);

    /* 3.3b 群内扩展 */
    if (p.extend) {
      var ex = el("section", "block extend");
      ex.appendChild(el("h3", "block-title", p.extend.title));
      ex.appendChild(el("p", "extend-text", p.extend.text));
      var legs = el("div", "extend-legs");
      p.extend.legs.forEach(function (l) {
        var row = el("div", "extend-leg");
        row.appendChild(el("span", "leg-route", l.route));
        row.appendChild(el("span", "leg-time", l.time));
        row.appendChild(el("span", "leg-price", l.price));
        row.appendChild(el("span", "leg-note", l.note));
        legs.appendChild(row);
      });
      ex.appendChild(legs);
      ex.appendChild(el("p", "extend-foot", "群内串联同样按 12306 实查：查询时间 " + T.meta.fareQueriedAt + "，参考乘车日 " + T.meta.fareRefDate + "。"));
      root.appendChild(ex);
    }

    /* 3.4 景点卡片 */
    var poiSec = el("section", "block");
    poiSec.appendChild(el("h3", "block-title", "值得玩的地方：≥2 张实景图 + 介绍 + 时长 + 门票"));
    var grid = el("div", "poi-grid");
    p.pois.forEach(function (poi) {
      var card = el("article", "poi");
      var shots = el("div", "shots");
      poi.imgs.forEach(function (id, idx) {
        var fig = el("figure", "shot");
        var im = el("img");
        im.src = imgSrc(id);
        im.alt = poi.name + " 实景 " + (idx + 1);
        im.loading = "lazy";
        fig.appendChild(im);
        fig.addEventListener("click", function () { openLightbox(id, poi.name); });
        fig.appendChild(el("span", "shot-zoom", "⤢"));
        shots.appendChild(fig);
      });
      card.appendChild(shots);

      var body = el("div", "poi-body");
      var title = el("div", "poi-title");
      title.appendChild(el("h4", null, poi.name));
      var tags = el("div", "tags");
      poi.tags.forEach(function (t) { tags.appendChild(el("span", "tag", t)); });
      title.appendChild(tags);
      body.appendChild(title);
      if (poi.intro) body.appendChild(el("p", "poi-intro", poi.intro));

      var facts = el("dl", "facts");
      [
        ["门票", poi.ticket],
        ["建议时长", poi.dur],
        ["开放时间", poi.hours],
        ["怎么去", poi.access]
      ].forEach(function (kv) {
        var row = el("div", "fact");
        row.appendChild(el("dt", null, kv[0]));
        row.appendChild(el("dd", null, kv[1]));
        facts.appendChild(row);
      });
      body.appendChild(facts);
      body.appendChild(el("p", "poi-tip", "提示：" + poi.tip));
      card.appendChild(body);
      grid.appendChild(card);
    });
    poiSec.appendChild(grid);
    root.appendChild(poiSec);

    /* 3.5 交通 */
    var trSec = el("section", "block");
    trSec.appendChild(el("h3", "block-title", "怎么去：12306 实查班次与二等座票价"));
    trSec.appendChild(transportTable("去程", p.transport.out, "out"));
    if (p.transport.back.length) trSec.appendChild(transportTable("回程", p.transport.back, "back"));

    if (p.transport.flights && p.transport.flights.length) {
      var fl = el("div", "flight-box");
      fl.appendChild(el("h4", "sub-title", "飞机备选（价格区间为估算，非实查）"));
      p.transport.flights.forEach(function (f) {
        var row = el("div", "flight-row");
        row.appendChild(el("span", "fl-route", f.route));
        row.appendChild(el("span", "fl-dur", f.dur));
        var pr = el("span", "fl-price", f.price);
        row.appendChild(pr);
        row.appendChild(el("span", "fl-note", f.note));
        fl.appendChild(row);
      });
      trSec.appendChild(fl);
    }
    var city = el("p", "city-transport");
    city.appendChild(el("strong", null, "市内交通："));
    city.appendChild(document.createTextNode(p.transport.city));
    trSec.appendChild(city);
    root.appendChild(trSec);

    /* 3.6 费用 */
    var costSec = el("section", "block");
    costSec.appendChild(el("h3", "block-title", "花多少钱：逐项拆开，标注实查 / 估算"));
    var calc = buildCostCalculator(p);
    costSec.appendChild(calc.node);
    var noteUl = el("ul", "cost-notes");
    p.costs.notes.forEach(function (n) { noteUl.appendChild(el("li", null, n)); });
    costSec.appendChild(noteUl);
    root.appendChild(costSec);

    /* 3.7 图片署名 */
    var creditSec = el("section", "block credits");
    creditSec.appendChild(el("h3", "block-title", "图片来源与许可"));
    var cUl = el("ul", "credit-list");
    var seen = {};
    var addCredit = function (id) {
      if (seen[id]) return;
      seen[id] = 1;
      var c = creditOf(id);
      var li = el("li");
      li.appendChild(el("span", "cr-file", /\./.test(id) ? id : id + ".jpg"));
      li.appendChild(el("span", "cr-meta", " · " + c.author + " · " + c.license + " · "));
      var a = el("a", null, "Wikimedia Commons");
      a.href = "https://commons.wikimedia.org/wiki/File:" + encodeURIComponent(c.file).replace(/%2F/g, "/").replace(/%3A/g, ":");
      a.target = "_blank";
      a.rel = "noopener";
      li.appendChild(a);
      cUl.appendChild(li);
    };
    addCredit(p.hero);
    p.pois.forEach(function (poi) {
      poi.imgs.forEach(addCredit);
    });
    creditSec.appendChild(cUl);
    root.appendChild(creditSec);
  }

  function transportTable(label, rows, kind) {
    var wrap = el("div", "tr-wrap");
    wrap.appendChild(el("h4", "sub-title", label));
    var scroll = el("div", "tr-scroll");
    var table = el("table", "tr-table");
    var thead = el("thead"), htr = el("tr");
    ["出发地", "方式", "车次", "区间", "时刻", "历时", "票价", "标记"].forEach(function (h) {
      htr.appendChild(el("th", null, h));
    });
    thead.appendChild(htr);
    table.appendChild(thead);
    var tb = el("tbody");
    rows.forEach(function (r) {
      var tr = el("tr");
      tr.appendChild(el("td", null, r.who));
      tr.appendChild(el("td", null, r.mode));
      tr.appendChild(el("td", "mono", r.train));
      tr.appendChild(el("td", null, r.route));
      tr.appendChild(el("td", "mono nowrap", r.time));
      tr.appendChild(el("td", null, r.dur));
      var tdP = el("td", "price");
      tdP.appendChild(el("strong", null, "¥" + (r.price % 1 === 0 ? r.price : r.price.toFixed(1))));
      tdP.appendChild(el("span", "cls", r.cls));
      tr.appendChild(tdP);
      var tdFlag = el("td");
      tdFlag.appendChild(el("span", "badge badge-real", "12306 实查"));
      tr.appendChild(tdFlag);
      tb.appendChild(tr);
      if (r.note) {
        var nt = el("tr", "tr-note");
        var td = el("td");
        td.colSpan = 8;
        td.textContent = r.note;
        nt.appendChild(td);
        tb.appendChild(nt);
      }
    });
    table.appendChild(tb);
    scroll.appendChild(table);
    wrap.appendChild(scroll);
    wrap.appendChild(el("p", "tr-foot",
      "票价来源：" + T.meta.source + "；查询时间 " + T.meta.fareQueriedAt +
      "；参考乘车日 " + T.meta.fareRefDate + "；适用出行日 " + T.meta.tripStart + " ~ " + T.meta.tripEnd +
      "。目标日车票尚未开售，实际成交价可能变动。"));
    return wrap;
  }

  /* ---------- 4. 费用计算器 ---------- */
  function buildCostCalculator(p) {
    var c = p.costs;
    var node = el("div", "calculator");

    var form = el("div", "calc-form");
    function field(label, value, min, max, step, suffix) {
      var wrap = el("label", "calc-field");
      wrap.appendChild(el("span", "cf-label", label));
      var input = el("input");
      input.type = "number";
      input.value = value;
      input.min = min; input.max = max; input.step = step || 1;
      wrap.appendChild(input);
      if (suffix) wrap.appendChild(el("span", "cf-suffix", suffix));
      form.appendChild(wrap);
      return input;
    }
    var inPeople = field("出行人数", 2, 1, 8, 1, "人");
    var inRooms = field("房间数", c.rooms, 1, 4, 1, "间");
    var inStay = field("住宿单价", c.stayPerNight, 100, 3000, 10, "元/晚");
    var inFood = field("餐饮标准", c.foodPerDay, 50, 800, 10, "元/人/天");
    node.appendChild(form);

    var out = el("div", "calc-out");
    node.appendChild(out);

    function money(n) { return "¥" + Math.round(n).toLocaleString("zh-CN"); }

    function compute() {
      var people = Math.max(1, +inPeople.value || 1);
      var rooms = Math.max(1, +inRooms.value || 1);
      var stay = Math.max(0, +inStay.value || 0);
      var food = Math.max(0, +inFood.value || 0);

      var stayTotal = stay * c.nights * rooms;
      var rows = [
        { k: "大交通（往返）", a: c.rail.A, b: c.rail.B, tag: "real" },
        { k: "住宿（" + c.nights + " 晚 × " + rooms + " 间，分摊）", a: stayTotal / people, b: stayTotal / people, tag: "est" },
        { k: "餐饮（" + c.days + " 天）", a: food * c.days, b: food * c.days, tag: "est" },
        { k: "市内交通（" + c.days + " 天）", a: c.localPerDay * c.days, b: c.localPerDay * c.days, tag: "est" },
        { k: "门票", a: c.tickets, b: c.tickets, tag: "est" },
        { k: "体验项目", a: c.experiences, b: c.experiences, tag: "est" }
      ];
      var subA = 0, subB = 0;
      rows.forEach(function (r) { subA += r.a; subB += r.b; });
      var bufA = subA * c.bufferPct / 100, bufB = subB * c.bufferPct / 100;

      out.innerHTML = "";
      var table = el("table", "cost-table");
      var thead = el("thead"), htr = el("tr");
      htr.appendChild(el("th", null, "项目"));
      htr.appendChild(el("th", null, c.rail.labelA));
      htr.appendChild(el("th", null, c.rail.labelB));
      htr.appendChild(el("th", null, "数据性质"));
      thead.appendChild(htr);
      table.appendChild(thead);
      var tb = el("tbody");
      rows.forEach(function (r) {
        var tr = el("tr");
        var tdK = el("td", null, r.k);
        tdK.appendChild(el("span", "badge badge-inline " + (r.tag === "real" ? "badge-real" : "badge-est"),
          r.tag === "real" ? "实查" : "估算"));
        tr.appendChild(tdK);
        tr.appendChild(el("td", "num", money(r.a)));
        tr.appendChild(el("td", "num", money(r.b)));
        var td = el("td");
        td.appendChild(el("span", "badge " + (r.tag === "real" ? "badge-real" : "badge-est"),
          r.tag === "real" ? "12306 实查" : "估算"));
        tr.appendChild(td);
        tb.appendChild(tr);
      });
      var trSub = el("tr", "row-sub");
      trSub.appendChild(el("td", null, "小计"));
      trSub.appendChild(el("td", "num", money(subA)));
      trSub.appendChild(el("td", "num", money(subB)));
      trSub.appendChild(el("td"));
      tb.appendChild(trSub);

      var trBuf = el("tr");
      trBuf.appendChild(el("td", null, "机动 " + c.bufferPct + "%"));
      trBuf.appendChild(el("td", "num", money(bufA)));
      trBuf.appendChild(el("td", "num", money(bufB)));
      trBuf.appendChild(el("td"));
      tb.appendChild(trBuf);

      var trTotal = el("tr", "row-total");
      trTotal.appendChild(el("td", null, "人均合计"));
      trTotal.appendChild(el("td", "num", money(subA + bufA)));
      trTotal.appendChild(el("td", "num", money(subB + bufB)));
      trTotal.appendChild(el("td"));
      tb.appendChild(trTotal);

      var trAll = el("tr", "row-all");
      var tdAll = el("td");
      tdAll.colSpan = 4;
      var allCell = el("div", "all-cell");
      allCell.appendChild(el("span", "all-label", "两人总支出"));
      allCell.appendChild(el("strong", "all-amt", money(subA + bufA + subB + bufB)));
      tdAll.appendChild(allCell);
      trAll.appendChild(tdAll);
      tb.appendChild(trAll);
      table.appendChild(tb);
      var cscroll = el("div", "cost-scroll");
      cscroll.appendChild(table);
      out.appendChild(cscroll);

      var bar = el("p", "budget-hint");
      bar.textContent = "对照示例预算人均 ¥2,700：上海出发 " + (subA + bufA <= 2700 ? "在预算内" : "超出 " + money(subA + bufA - 2700)) +
        "；广州出发 " + (subB + bufB <= 2700 ? "在预算内" : "超出 " + money(subB + bufB - 2700)) + "。";
      out.appendChild(bar);
    }

    [inPeople, inRooms, inStay, inFood].forEach(function (i) {
      i.addEventListener("input", compute);
    });
    compute();
    return { node: node };
  }

  /* ---------- 5. 灯箱 ---------- */
  function openLightbox(id, title) {
    var c = creditOf(id);
    var lb = $("#lightbox");
    var im = $("#lb-img");
    im.src = imgSrc(id);
    im.alt = title;
    $("#lb-cap").textContent = title + " · 图：" + c.author + " / " + c.license;
    lb.classList.add("open");
    lb.setAttribute("aria-hidden", "false");
    document.body.classList.add("no-scroll");
  }
  function closeLightbox() {
    var lb = $("#lightbox");
    lb.classList.remove("open");
    lb.setAttribute("aria-hidden", "true");
    document.body.classList.remove("no-scroll");
  }

  /* ---------- 6. 导航高亮 ---------- */
  function initNav() {
    var links = $$(".nav a");
    var sections = links.map(function (a) { return $(a.getAttribute("href")); }).filter(Boolean);
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          links.forEach(function (a) {
            a.classList.toggle("active", a.getAttribute("href") === "#" + e.target.id);
          });
        }
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    sections.forEach(function (s) { io.observe(s); });

    $("#lb-close").addEventListener("click", closeLightbox);
    $("#lightbox").addEventListener("click", function (e) {
      if (e.target.id === "lightbox") closeLightbox();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeLightbox();
    });
  }

  /* ---------- boot ---------- */
  renderMeta();
  renderProfile();
  renderScore();
  renderPlanTabs();
  renderPlan();
  initNav();

  document.documentElement.classList.add("js-ready");
})();

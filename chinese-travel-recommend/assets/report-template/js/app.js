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
      if (r.d.seasonStatus && r.d.seasonStatus !== "ok") {
        tdName.appendChild(el("span", "badge season-" + r.d.seasonStatus,
          r.d.seasonStatus === "closed" ? "闭园/停航" : "非当季"));
      }
      if (r.d.userPicked) {
        var pickText = "你点名";
        if (r.d.overBudget > 0) pickText += " · 超 ¥" + Math.round(r.d.overBudget).toLocaleString("zh-CN");
        tdName.appendChild(el("span", "badge badge-pick", pickText));
      }
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
      if (r.d.seasonNote) tdNote.appendChild(el("span", "note-season", "季节：" + r.d.seasonNote));
      tdNote.appendChild(el("span", "note-link", "群内：" + r.d.link));
      trNote.appendChild(tdNote);
      tbody.appendChild(trNote);
    });
    table.appendChild(tbody);

    if (T.meta.exclusion) {
      var ex = T.meta.exclusion;
      var wrap = $("#score .wrap") || table.parentNode;
      var stale = wrap.querySelector(".exclusion");
      if (stale) stale.parentNode.removeChild(stale);
      var box = el("div", "card exclusion");
      box.appendChild(el("h3", null, ex.confirmed ? "已替你排除" : "未确认是否去过"));
      var list = el("ul", "excl-list");
      (ex.items || []).forEach(function (item) {
        list.appendChild(el("li", null,
          item.place + " — " + item.reason + (item.replaced_by ? "（替换为 " + item.replaced_by + "）" : "")));
      });
      if (!(ex.items || []).length) {
        list.appendChild(el("li", null, "本次没有整群替换：你确认过 6 个群都没去过，也没有明确不想去的。"));
      }
      box.appendChild(list);
      if (ex.note) box.appendChild(el("p", "card-sub", ex.note));
      wrap.appendChild(box);
    }

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
      b.appendChild(el("span", "tab-verdict", p.verdict));
      b.addEventListener("click", function () { activePlan = k; renderPlanTabs(); renderPlan(); });
      nav.appendChild(b);
    });
  }

  function renderSvgMap(p) {
    if (!p.geo || !p.geo.cities || !p.geo.cities.length) return null;
    var NS = "http://www.w3.org/2000/svg";
    var cities = p.geo.cities;
    var pois = (p.pois || []).filter(function (x) { return x.geo && x.geo.lat != null; });
    var all = cities.concat(pois.map(function (x) { return { lat: x.geo.lat, lng: x.geo.lng }; }));
    var lat0 = all.reduce(function (s, x) { return s + x.lat; }, 0) / all.length * Math.PI / 180;
    function proj(x) { return { x: x.lng * Math.cos(lat0), y: -x.lat }; }
    var q = all.map(proj);
    var minX = Math.min.apply(null, q.map(function (v) { return v.x; }));
    var maxX = Math.max.apply(null, q.map(function (v) { return v.x; }));
    var minY = Math.min.apply(null, q.map(function (v) { return v.y; }));
    var maxY = Math.max.apply(null, q.map(function (v) { return v.y; }));
    var W = 720, H = 350, pad = 58;
    var s = Math.min((W - 2 * pad) / (maxX - minX || 1), (H - 2 * pad) / (maxY - minY || 1));
    var ox = pad + ((W - 2 * pad) - (maxX - minX) * s) / 2;
    var oy = pad + ((H - 2 * pad) - (maxY - minY) * s) / 2;
    function xy(x) {
      var v = proj(x);
      return [ox + (v.x - minX) * s, oy + (v.y - minY) * s];
    }
    var fig = el("figure", "plan-map");
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", p.name + " 路线示意图");

    var line = document.createElementNS(NS, "polyline");
    line.setAttribute("points", cities.map(function (c) {
      var v = xy(c);
      return v[0].toFixed(1) + "," + v[1].toFixed(1);
    }).join(" "));
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", "var(--accent)");
    line.setAttribute("stroke-width", "2");
    line.setAttribute("stroke-dasharray", "6 6");
    line.setAttribute("opacity", ".5");
    svg.appendChild(line);

    cities.forEach(function (c) {
      var v = xy(c);
      var dot = document.createElementNS(NS, "circle");
      dot.setAttribute("cx", v[0]);
      dot.setAttribute("cy", v[1]);
      dot.setAttribute("r", "5");
      dot.setAttribute("fill", "var(--ink)");
      svg.appendChild(dot);
      var t = document.createElementNS(NS, "text");
      t.setAttribute("x", v[0]);
      t.setAttribute("y", v[1] - 13);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("font-size", "13");
      t.setAttribute("font-weight", "600");
      t.setAttribute("fill", "var(--ink)");
      t.textContent = c.name;
      svg.appendChild(t);
    });

    // 同城景点常落在同一条街上：投影后距离过近就沿连线双向推开，保证编号可读
    var pts = pois.map(function (poi) {
      var v = xy(poi.geo);
      return [v[0] + (poi.geo.jx || 0), v[1] + (poi.geo.jy || 0)];
    });
    var moved = false;
    var MIN_GAP = 26;
    for (var a = 0; a < pts.length; a++) {
      for (var b = a + 1; b < pts.length; b++) {
        var dx = pts[b][0] - pts[a][0], dy = pts[b][1] - pts[a][1];
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist >= MIN_GAP) continue;
        if (dist < 0.5) { dx = 1; dy = -1; dist = Math.SQRT2; }
        var push = (MIN_GAP - dist) / 2 + 1;
        var ux = dx / dist, uy = dy / dist;
        pts[a][0] -= ux * push; pts[a][1] -= uy * push;
        pts[b][0] += ux * push; pts[b][1] += uy * push;
        moved = true;
      }
    }

    pois.forEach(function (poi, i) {
      var v = pts[i];
      var ring = document.createElementNS(NS, "circle");
      ring.setAttribute("cx", v[0]);
      ring.setAttribute("cy", v[1]);
      ring.setAttribute("r", "10");
      ring.setAttribute("fill", "var(--surface)");
      ring.setAttribute("stroke", "var(--accent)");
      ring.setAttribute("stroke-width", "2");
      svg.appendChild(ring);
      var num = document.createElementNS(NS, "text");
      num.setAttribute("x", v[0]);
      num.setAttribute("y", v[1] + 4);
      num.setAttribute("text-anchor", "middle");
      num.setAttribute("font-size", "11");
      num.setAttribute("font-weight", "700");
      num.setAttribute("fill", "var(--accent)");
      num.textContent = String(i + 1);
      svg.appendChild(num);
      var right = v[0] < W - 150;
      var lab = document.createElementNS(NS, "text");
      lab.setAttribute("x", v[0] + (right ? 15 : -15));
      lab.setAttribute("y", v[1] + 4);
      lab.setAttribute("text-anchor", right ? "start" : "end");
      lab.setAttribute("font-size", "11");
      lab.setAttribute("fill", "var(--muted)");
      lab.textContent = poi.name;
      svg.appendChild(lab);
    });

    fig.appendChild(svg);
    var dense = moved || pois.some(function (poi) { return poi.geo.jx || poi.geo.jy; });
    fig.appendChild(el("figcaption", "map-cap",
      "示意地图 · 按经纬度等距圆柱投影绘制，非瓦片底图；数字对应下方景点卡片顺序。" +
      (dense ? "密集点位已做小幅屏幕避让。" : "")));
    return fig;
  }

  var amapLoading = null;
  function loadAmap(key, security) {
    if (window.AMap && window.AMap.Map) return Promise.resolve(window.AMap);
    if (amapLoading) return amapLoading;
    amapLoading = new Promise(function (resolve, reject) {
      if (security) window._AMapSecurityConfig = { securityJsCode: security };
      var script = document.createElement("script");
      script.src = "https://webapi.amap.com/loader.js";
      script.onload = function () {
        if (!window.AMapLoader) { reject(new Error("AMapLoader 未加载")); return; }
        window.AMapLoader.load({ key: key, version: "2.0" }).then(resolve).catch(reject);
      };
      script.onerror = function () { reject(new Error("高德脚本加载失败")); };
      document.head.appendChild(script);
    });
    return amapLoading;
  }

  function renderAmap(p) {
    var fig = el("figure", "plan-map");
    var box = el("div", "amap-box");
    fig.appendChild(box);
    fig.appendChild(el("figcaption", "map-cap",
      "高德地图 · 需联网加载；点位按经纬度定位，数字顺序同下方景点卡片。"));
    loadAmap(T.meta.amapKey, T.meta.amapSecurity).then(function (AMap) {
      var first = p.geo.cities[0];
      var map = new AMap.Map(box, { zoom: 8, center: [first.lng, first.lat], viewMode: "2D" });
      var path = p.geo.cities.map(function (c) { return [c.lng, c.lat]; });
      if (path.length > 1) {
        map.add(new AMap.Polyline({
          path: path, strokeColor: "#a8432a", strokeWeight: 3, strokeStyle: "dashed"
        }));
      }
      p.geo.cities.forEach(function (c) {
        map.add(new AMap.Marker({
          position: [c.lng, c.lat], title: c.name, zIndex: 300,
          content: '<span class="amap-city">' + c.name + "</span>",
          offset: new AMap.Pixel(-18, -38)
        }));
      });
      var placed = [];
      (p.pois || []).forEach(function (poi, i) {
        if (!poi.geo) return;
        // 同城景点常在同一条街上：与已放置的点太近就沿对角线错开，避免编号糊在一起
        var offX = 0, offY = 0;
        placed.forEach(function (q) {
          if (Math.abs(q.lat - poi.geo.lat) < 0.02 && Math.abs(q.lng - poi.geo.lng) < 0.02) {
            offX += 19;
            offY -= 17;
          }
        });
        placed.push({ lat: poi.geo.lat, lng: poi.geo.lng });
        map.add(new AMap.Marker({
          position: [poi.geo.lng, poi.geo.lat], title: poi.name, zIndex: 100 + i,
          content: '<span class="amap-pin">' + (i + 1) + "</span>",
          offset: new AMap.Pixel(-11 + offX, -11 + offY)
        }));
      });
      map.setFitView();
    }).catch(function () {
      var fallback = renderSvgMap(p);
      if (!fallback) {
        fig.innerHTML = "";
        fig.appendChild(el("figcaption", "map-cap", "地图数据缺失：请补 geo.cities 与景点 geo。"));
        return;
      }
      var note = fallback.querySelector(".map-cap");
      if (note) note.textContent += "（高德地图加载失败，已自动切回离线 SVG）";
      if (fig.parentNode) fig.parentNode.replaceChild(fallback, fig);
    });
    return fig;
  }

  function renderMap(p) {
    if (T.meta && T.meta.mapMode === "amap" && T.meta.amapKey) return renderAmap(p);
    return renderSvgMap(p);
  }

  function clusterOfPlan(p) {
    var label = p.clusterLabel || "";
    for (var i = 0; i < (T.clusters || []).length; i++) {
      if (label.indexOf(T.clusters[i].name) === 0) return T.clusters[i];
    }
    return null;
  }

  function renderPlan() {
    var p = T.plans[activePlan];
    var root = $("#plan-body");
    root.innerHTML = "";
    var planTitle = $("#plan-title");
    if (planTitle) {
      planTitle.textContent = "推荐方案：" + p.name + (T.meta.tripDays ? " · " + T.meta.tripDays + " 天" : "");
    }

    var planCluster = clusterOfPlan(p);
    if (planCluster && planCluster.seasonStatus && planCluster.seasonStatus !== "ok") {
      var alertBox = el("div", "season-alert " + planCluster.seasonStatus);
      alertBox.appendChild(el("strong", null,
        planCluster.seasonStatus === "closed" ? "季节提示：闭园 / 停航" : "季节提示：非当季"));
      alertBox.appendChild(document.createTextNode(
        " " + (planCluster.seasonNote || "这个月份不适合，换季再来。")));
      root.appendChild(alertBox);
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
    head.appendChild(heroWrap);
    root.appendChild(head);

    var map = renderMap(p);
    if (map) root.appendChild(map);

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
    poiSec.appendChild(el("h3", "block-title", "值得玩的地方：实景图（目标 4–6 张，地标 6–10）+ 介绍 + 时长 + 门票"));
    var grid = el("div", "poi-grid");
    p.pois.forEach(function (poi) {
      var card = el("article", "poi");
      var shots = el("div", "shots");
      if (!poi.imgs || !poi.imgs.length) {
        shots.appendChild(el("div", "shot-empty", poi.noImageNote || "暂无实景图：公开来源未收录这个点位"));
      }
      (poi.imgs || []).forEach(function (id, idx) {
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
      if (poi.status && poi.status !== "open") {
        var statusLabels = { "off-season": "非当季", closed: "暂停开放", limited: "限流/部分开放" };
        var badge = el("span", "poi-status " + poi.status, statusLabels[poi.status] || poi.status);
        if (poi.statusNote) badge.title = poi.statusNote;
        title.appendChild(badge);
      }
      var tags = el("div", "tags");
      poi.tags.forEach(function (t) { tags.appendChild(el("span", "tag", t)); });
      title.appendChild(tags);
      body.appendChild(title);
      if (poi.intro) body.appendChild(el("p", "poi-intro", poi.intro));

      var facts = el("dl", "facts");
      var factRows = [
        ["门票", poi.ticket],
        ["建议时长", poi.dur],
        ["开放时间", poi.hours]
      ];
      if (poi.entry) factRows.push(["入口", poi.entry]);
      factRows.push(["怎么去", poi.access]);
      factRows.forEach(function (kv) {
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
    trSec.appendChild(el("h3", "block-title", "怎么去：高铁 12306 实查，机票为区间估算"));
    if (p.transport.out && p.transport.out.length) trSec.appendChild(transportTable("去程", p.transport.out, "out"));
    if (p.transport.back && p.transport.back.length) trSec.appendChild(transportTable("回程", p.transport.back, "back"));

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

    if (p.sources && p.sources.length) {
      var srcSec = el("section", "block sources");
      srcSec.appendChild(el("h3", "block-title", "本方案情报来源：官方公告与本地经验"));
      var intel = el("ul", "intel-list");
      p.sources.forEach(function (s) {
        var li = el("li");
        li.appendChild(el("span", "intel-claim", s.claim));
        li.appendChild(el("span", "intel-meta", s.source + " · 核对 " + s.date));
        intel.appendChild(li);
      });
      srcSec.appendChild(intel);
      srcSec.appendChild(el("p", "intel-foot",
        "门票、开放时间、预约规则以景区当日公告为准；本地经验只用于错峰、入口、价格等体验层信息。"));
      root.appendChild(srcSec);
    }
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
      var est = r.tag === "est" || /飞机|航班/.test((r.mode || "") + (r.cls || ""));
      tdFlag.appendChild(el("span", "badge " + (est ? "badge-est" : "badge-real"), est ? "估算" : "12306 实查"));
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
        { k: "大交通（往返）", a: c.rail.A, b: c.rail.B, tagA: c.rail.tagA || "est", tagB: c.rail.tagB || "est" },
        { k: "住宿（" + c.nights + " 晚 × " + rooms + " 间，分摊）", a: stayTotal / people, b: stayTotal / people, tagA: "est", tagB: "est" },
        { k: "餐饮（" + c.days + " 天）", a: food * c.days, b: food * c.days, tagA: "est", tagB: "est" },
        { k: "市内交通（" + c.days + " 天）", a: c.localPerDay * c.days, b: c.localPerDay * c.days, tagA: "est", tagB: "est" },
        { k: "门票", a: c.tickets, b: c.tickets, tagA: "est", tagB: "est" },
        { k: "体验项目", a: c.experiences, b: c.experiences, tagA: "est", tagB: "est" }
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
        tr.appendChild(el("td", null, r.k));
        [[r.a, r.tagA], [r.b, r.tagB]].forEach(function (pair) {
          var td = el("td", "num");
          td.appendChild(document.createTextNode(money(pair[0]) + " "));
          td.appendChild(el("span", "badge badge-inline " + (pair[1] === "real" ? "badge-real" : "badge-est"),
            pair[1] === "real" ? "实查" : "估算"));
          tr.appendChild(td);
        });
        tr.appendChild(el("td", null, "按侧标注"));
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
      var sideA = subA + bufA, sideB = subB + bufB;
      var mode = T.meta.budgetMode || "per_person";
      function rel(value, cap) {
        return value <= cap ? "在预算内，余 " + money(cap - value) : "超出 " + money(value - cap);
      }
      var text = "";
      if (mode === "shared" && T.meta.budgetCap) {
        var totalCap = T.meta.budgetCap;
        var totalSpend = sideA + sideB;
        text = "两人合计 " + money(totalSpend) + "，对照共同预算 " + money(totalCap) + "：" +
          (totalSpend <= totalCap
            ? "在预算内，余 " + money(totalCap - totalSpend)
            : "超出 " + money(totalSpend - totalCap)) +
          "（" + c.rail.labelA + " " + money(sideA) + " / " + c.rail.labelB + " " + money(sideB) + "）。";
      } else {
        var capA = T.meta.budgetCapA != null ? T.meta.budgetCapA : T.meta.budgetCap;
        var capB = T.meta.budgetCapB != null ? T.meta.budgetCapB : capA;
        if (capA != null || capB != null) {
          capA = capA == null ? capB : capA;
          capB = capB == null ? capA : capB;
          if (mode === "uniform") {
            var high = Math.max(capA, capB), low = Math.min(capA, capB);
            text = "统一上限 " + money(high) + "：" + c.rail.labelA + " " + rel(sideA, high) +
              "；" + c.rail.labelB + " " + rel(sideB, high) +
              "。按较低上限 " + money(low) + " 两人合计超出 " +
              money(Math.max(0, sideA - low) + Math.max(0, sideB - low)) + "。";
          } else {
            text = "各自上限：" + c.rail.labelA + " " + money(capA) + " " + rel(sideA, capA) +
              "；" + c.rail.labelB + " " + money(capB) + " " + rel(sideB, capB) + "。";
          }
        }
      }
      if (text) {
        bar.textContent = text;
        out.appendChild(bar);
      }
    }

    [inPeople, inRooms, inStay, inFood].forEach(function (i) {
      i.addEventListener("input", compute);
    });
    compute();
    return { node: node };
  }

  /* ---------- 5. 灯箱 ---------- */
  function openLightbox(id, title) {
    var lb = $("#lightbox");
    var im = $("#lb-img");
    im.src = imgSrc(id);
    im.alt = title;
    $("#lb-cap").textContent = title;
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

/* ==========================================================================
   模板数据 —— 复制本目录后，先改这个文件，再替换 images/ 里的占位图。
   改完把 meta.isTemplate 改成 false，否则页面顶部会一直挂「模板占位」横幅。
   ========================================================================== */

window.TRIP = {
  meta: {
    isTemplate: true,
    title: "示例目的地 · 4 天",
    subtitle: "一句话说清这次推荐的取舍（示例，请替换）",
    builtAt: "2026-01-01",
    fareQueriedAt: "2026-01-01 10:00 (UTC+8)",
    fareRefDate: "2026-01-08",
    tripStart: "2026-02-01",
    tripEnd: "2026-02-04",
    tripDays: 4,
    budgetCap: 2700,
    budgetCapA: 2700,
    budgetCapB: 2700,
    budgetMode: "per_person",
    mapMode: "svg",
    amapKey: "",
    amapSecurity: "",
    chips: ["4 天 3 晚", "示例出发地 A + B", "人均 ¥2k–3k", "推荐单位：地点群"],
    currency: "CNY",
    source: "中国铁路 12306 官方接口（queryG / queryTicketPrice 实查）",
    presale: {
      observed: "示例：2026-01-01 实测可售至 2026-01-15；再往后返回空，说明尚未开售。",
      conclusion: "示例：出行日车票尚未开售，价格取同车次近期售价。",
      risk: "示例：开售后可能浮动，表中价格不是出行日成交价。"
    }
  },

  /* ---------------- 1. 需要用户补充的画像字段 ---------------- */
  profileFields: [
    { key: "origin", label: "出发城市 / 车站或机场", why: "决定大交通方式与时长，是第一道硬条件", example: "上海虹桥", required: true },
    { key: "companionFrom", label: "同行者所在地 + 人数 + 关系", why: "多地出发时要找会合成本最低的目的地群", example: "广州南，1 人，朋友", required: true },
    { key: "dates", label: "出行日期与可浮动范围", why: "假期前后价差可达数倍", example: "2026-02-01 ~ 02-04，可浮动 1 天", required: true },
    { key: "duration", label: "假期长度（含在途）", why: "决定群里有几个城市", example: "4 天 3 晚", required: true },
    { key: "budget", label: "预算上限（人均 / 总）", why: "先定上限再选群", example: "人均 3000 元（含大交通）", required: true },
    { key: "budgetMode", label: "预算口径：共同 / 各自 / 统一", why: "多人不同上限时决定怎么算超支", example: "各自上限：A ¥4000 / B ¥3000", required: true },
    { key: "transport", label: "交通偏好与可接受最长在途", why: "决定高铁还是飞机、能否跨城", example: "高铁优先，单程 ≤ 7 小时", required: false },
    { key: "interests", label: "兴趣权重", why: "决定评分权重", example: "人文 40% / 美食 40% / 摄影 20%", required: false },
    { key: "pace", label: "体力与节奏", why: "决定每天排几个点", example: "中等，日均 1.2 万步", required: false },
    { key: "climate", label: "气候偏好", why: "1 月南北温差近 40℃，直接淘汰一半选项", example: "避寒，白天 ≥ 12℃", required: false },
    { key: "stay", label: "住宿档次与房型", why: "住宿常占 25–35%", example: "双床房 1 间，¥350–450/晚", required: false },
    { key: "diet", label: "饮食禁忌 / 过敏", why: "影响选店", example: "不吃香菜", required: false },
    { key: "hard", label: "必去 / 排除 / 返程硬约束", why: "如「必须 4 日晚回，5 日上班」", example: "1/4 22:00 前到家", required: false }
  ],

  sampleProfile: {
    origin: "示例：出发地 A",
    companion: "示例：同行者 B · 1 人 · 朋友",
    dates: "示例：2026-02-01 → 02-04（4 天 3 晚）",
    budget: "示例：人均 ¥3000",
    style: "示例：人文 + 美食，中等节奏"
  },

  /* ---------------- 2. 评分权重 ---------------- */
  dims: [
    { key: "season", label: "季节体感", w: 18 },
    { key: "culture", label: "人文风土", w: 20 },
    { key: "food", label: "美食密度", w: 18 },
    { key: "access", label: "双城可达", w: 16 },
    { key: "link", label: "群内串联", w: 10 },
    { key: "cost", label: "预算友好", w: 10 },
    { key: "crowd", label: "人流舒适", w: 8 }
  ],

  presets: [
    { id: "culture", name: "人文美食（当前）", w: { season: 18, culture: 20, food: 18, access: 16, link: 10, cost: 10, crowd: 8 } },
    { id: "budget", name: "省心省钱", w: { season: 12, culture: 8, food: 12, access: 18, link: 18, cost: 24, crowd: 8 } },
    { id: "family", name: "亲子 / 自然", w: { season: 22, culture: 8, food: 8, access: 18, link: 14, cost: 12, crowd: 18 } }
  ],

  /* ---------------- 3. 5–7 个风格互斥的地点群（必填，每个群都要有对应方案） ---------------- */
  clusters: [
    {
      id: "c1", name: "示例人文群", style: "人文 · 古城",
      cities: ["示例城A", "示例城B"], days: "3–5 天", fit: [3, 5],
      link: "示例城A ↔ 示例城B 动车 30 分钟，¥50",
      seasonStatus: "ok", seasonNote: "示例：当季，白天 15℃ 左右",
      userPicked: false, overBudget: null,
      s: { season: 4, culture: 5, food: 4, access: 4, link: 5, cost: 4, crowd: 4 },
      note: "为什么会进前五：一句话说清「为什么是它」和「为什么不是第二名」。"
    },
    {
      id: "c2", name: "示例美食群", style: "美食 · 市集",
      cities: ["示例城C", "示例城D"], days: "2–4 天", fit: [2, 4],
      link: "示例城C ↔ 示例城D 城际 25 分钟，¥15",
      seasonStatus: "ok", seasonNote: "示例：全年可去，避开节假日排队",
      userPicked: false, overBudget: null,
      s: { season: 4, culture: 3, food: 5, access: 3, link: 5, cost: 5, crowd: 4 },
      note: "以吃为主线；写清哪座城吃早、哪座城吃夜宵。"
    },
    {
      id: "c3", name: "示例海滨群", style: "海滨 · 度假",
      cities: ["示例城E", "示例城F", "示例城G"], days: "5–7 天", fit: [5, 7],
      link: "E→F 高铁 1h40；F→G 轮渡 40 分钟",
      seasonStatus: "off", seasonNote: "示例：冬季停航/风大，换季再来",
      userPicked: false, overBudget: null,
      s: { season: 2, culture: 3, food: 4, access: 2, link: 4, cost: 3, crowd: 3 },
      note: "三城同质必须合并成一泳线；4 天窗口不成立。"
    },
    {
      id: "c4", name: "示例古都群", style: "历史 · 古都",
      cities: ["示例城H", "示例山I"], days: "4–5 天", fit: [4, 5],
      link: "H 城 → I 山 高铁 35 分钟",
      seasonStatus: "ok", seasonNote: "示例：秋季最好，冬季山岳项目看天气",
      userPicked: false, overBudget: null,
      s: { season: 2, culture: 5, food: 4, access: 3, link: 4, cost: 4, crowd: 3 },
      note: "人文最厚，但冬季体感差；山岳项目受天气影响。"
    },
    {
      id: "c5", name: "示例冰雪群", style: "冰雪 · 冬季限定",
      cities: ["示例城J", "示例镇K"], days: "4–6 天", fit: [4, 6],
      link: "J 城 → K 镇 高铁 1.5 小时",
      seasonStatus: "ok", seasonNote: "示例：12–2 月是冰雪季",
      userPicked: true, overBudget: 800,
      s: { season: 1, culture: 3, food: 4, access: 2, link: 4, cost: 2, crowd: 2 },
      note: "季节限定，溢价最高；对短假不友好。"
    }
  ],

  /* ---------------- 4. 图片署名（每张都要有） ---------------- */
  credits: {
    "placeholder-1.svg": { author: "模板占位", license: "CC0", file: "placeholder-1.svg" },
    "placeholder-2.svg": { author: "模板占位", license: "CC0", file: "placeholder-2.svg" },
    "placeholder-3.svg": { author: "模板占位", license: "CC0", file: "placeholder-3.svg" },
    "placeholder-4.svg": { author: "模板占位", license: "CC0", file: "placeholder-4.svg" }
  },

  /* ---------------- 5. 详细方案（复制整段即可新增） ---------------- */
  plans: {
    demo: {
      id: "demo",
      name: "示例目的地",
      tagline: "一句话定位 · 一句最有画面感的描述",
      verdict: "模板占位",
      clusterLabel: "示例人文群 · 主城",
      geo: { cities: [
        { name: "示例城A", lat: 31.230, lng: 121.470 },
        { name: "示例城B", lat: 30.270, lng: 120.160 }
      ] },
      hero: "placeholder-1.svg",
      why: [
        "第一条理由：用数据说话（车程、票价、天数），不要写形容词。",
        "第二条理由：内容密度或季节优势，能给具体数字就给。",
        "第三条理由：为什么不是第二名——把取舍讲清楚。"
      ],
      customs: [
        { t: "风土人情条目一", d: "写具体的历史、宗教、工艺或民俗，不要写「历史悠久、风景优美」。" },
        { t: "风土人情条目二", d: "写本地人的日常：几点吃什么、怎么称呼、什么季节做什么。" }
      ],
      days: [
        {
          n: 1, date: "D1", theme: "抵达 · 主线",
          items: [
            { time: "09:00–13:00", what: "出发地 → 目的地（车次/航班 + 时长）", dur: "在途", kind: "move" },
            { time: "14:00", what: "入住 + 第一个轻项目（步行范围内）", dur: "1.5 h", kind: "sight" },
            { time: "18:00", what: "晚餐：本地菜，写店名类型与人均", dur: "1 h", kind: "food" }
          ]
        }
      ],
      pois: [
        {
          name: "景点一", imgs: ["placeholder-1.svg", "placeholder-2.svg"],
          geo: { lat: 31.232, lng: 121.475 },
          ticket: "免费（以公告为准）", dur: "2 h", hours: "08:00–17:30",
          status: "open", entry: "1 号门（南门）",
          access: "从住处步行 10 分钟",
          intro: "60–150 字：是什么、为什么值得、看什么。要跟上面的风土人情呼应，而不是重复门票信息。",
          tip: "一条与介绍不重复的实用信息：错峰时段、入口、排号、着装。",
          tags: ["世遗", "摄影"]
        },
        {
          name: "景点二", imgs: ["placeholder-3.svg", "placeholder-4.svg"],
          geo: { lat: 30.275, lng: 120.155 },
          ticket: "约 ¥50（估算，以公告为准）", dur: "1.5 h", hours: "09:00–17:00",
          status: "open", entry: "东门游客中心",
          access: "打车 15 分钟，约 ¥30",
          intro: "第二处景点同样要写「是什么 / 为什么值得 / 看什么」，不要只写一句「很值得去」。",
          tip: "写本地人给的细节，例如几点人最少、从哪个门进。",
          tags: ["人文"]
        }
      ],
      extend: {
        title: "群内扩展：+1 天去邻城",
        text: "说明多一天去哪、为什么值得、返程怎么走；不占用本次行程。",
        legs: [
          { route: "主城 → 邻城", time: "30 分钟", price: "¥50", note: "车次/船班示例" }
        ]
      },
      transport: {
        out: [
          { who: "出发地 A", mode: "高铁", train: "G0000", route: "A 站 → 目的地站", time: "09:00 → 13:00", dur: "4h00", price: 300, cls: "二等座" },
          { who: "出发地 B", mode: "高铁", train: "G0001", route: "B 站 → 目的地站", time: "08:00 → 11:30", dur: "3h30", price: 260, cls: "二等座", note: "备注：为什么选它" }
        ],
        back: [
          { who: "出发地 A", mode: "高铁", train: "G0002", route: "目的地站 → A 站", time: "16:00 → 20:30", dur: "4h30", price: 300, cls: "二等座" }
        ],
        flights: [
          { route: "A 机场 → 目的地机场", dur: "约 2h", price: "¥700–1200（估算）", note: "含接驳总耗时与高铁对比" }
        ],
        city: "市内交通：哪些点步行可达、打车大概多少钱、公交/地铁怎么坐。"
      },
      costs: {
        rail: { A: 600, B: 520, labelA: "出发地 A 往返", labelB: "出发地 B 往返" },
        stayPerNight: 400, nights: 3, rooms: 1,
        foodPerDay: 130, days: 4,
        localPerDay: 35,
        tickets: 50,
        experiences: 100,
        bufferPct: 10,
        notes: [
          "住宿：写清按什么标准估的，元旦/春节可能上浮多少。",
          "门票：写清免费项与收费项。",
          "体验：写清包含什么、价格区间。"
        ]
      }
    }
  }
};

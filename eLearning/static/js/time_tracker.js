/**
 * TimeTracker — localStorage-based page time tracker
 * Saves sessions as: [{page, date, seconds}, ...]
 */
(function () {
    const STORAGE_KEY = 'oo_time_sessions';
    const SAVE_INTERVAL = 30; // seconds

    let pageKey = document.documentElement.dataset.trackerPage || 'dashboard';
    let sessionStart = Date.now();
    let accumulated = 0;   // seconds accumulated this page visit
    let displayEl = null;
    let totalEl = null;
    let ticker = null;

    /* ── Storage helpers ── */
    function load() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || []; }
        catch (e) { return []; }
    }

    function save(secs) {
        if (secs <= 0) return;
        const sessions = load();
        const today = todayStr();
        const existing = sessions.find(s => s.page === pageKey && s.date === today);
        if (existing) {
            existing.seconds += secs;
        } else {
            sessions.push({ page: pageKey, date: today, seconds: secs });
        }
        // keep last 365 entries per page
        const kept = sessions.filter(s => s.page !== pageKey).concat(
            sessions.filter(s => s.page === pageKey).slice(-365)
        );
        localStorage.setItem(STORAGE_KEY, JSON.stringify(kept));
    }

    function todayStr() {
        return new Date().toISOString().slice(0, 10);
    }

    /* ── Period filter ── */
    function periodDates(period) {
        const now = new Date();
        let start;
        if (period === 'day') {
            start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        } else if (period === 'week') {
            const day = now.getDay() || 7;
            start = new Date(now);
            start.setDate(now.getDate() - day + 1);
            start.setHours(0, 0, 0, 0);
        } else if (period === 'month') {
            start = new Date(now.getFullYear(), now.getMonth(), 1);
        } else { // year
            start = new Date(now.getFullYear(), 0, 1);
        }
        return start.toISOString().slice(0, 10);
    }

    function totalForPeriod(period) {
        const sessions = load();
        const from = periodDates(period);
        return sessions
            .filter(s => s.page === pageKey && s.date >= from)
            .reduce((acc, s) => acc + s.seconds, 0);
    }

    /* ── Formatting ── */
    function fmt(totalSec) {
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        if (h > 0) return `${h}h ${pad(m)}m ${pad(s)}s`;
        if (m > 0) return `${m}m ${pad(s)}s`;
        return `${s}s`;
    }

    function fmtClock(totalSec) {
        const h = Math.floor(totalSec / 3600);
        const m = Math.floor((totalSec % 3600) / 60);
        const s = totalSec % 60;
        return `${pad(h)}:${pad(m)}:${pad(s)}`;
    }

    function pad(n) { return String(n).padStart(2, '0'); }

    /* ── Tick ── */
    function tick() {
        accumulated = Math.floor((Date.now() - sessionStart) / 1000);

        if (displayEl) displayEl.textContent = fmtClock(accumulated);

        // auto-save every SAVE_INTERVAL seconds
        if (accumulated > 0 && accumulated % SAVE_INTERVAL === 0) {
            save(SAVE_INTERVAL);
        }

        refreshTotal();
    }

    function refreshTotal() {
        if (!totalEl) return;
        const period = document.querySelector('.tt-filter-btn.active')?.dataset.period || 'day';
        const saved = totalForPeriod(period);
        totalEl.textContent = fmt(saved + accumulated);
    }

    /* ── Save remaining on leave ── */
    function saveRemaining() {
        const elapsed = Math.floor((Date.now() - sessionStart) / 1000);
        const remainder = elapsed % SAVE_INTERVAL;
        if (remainder > 0) save(remainder);
    }

    window.addEventListener('beforeunload', saveRemaining);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) saveRemaining();
        else sessionStart = Date.now() - accumulated * 1000;
    });

    /* ── Public API ── */
    window.TimeTracker = {
        init(liveEl, totEl) {
            displayEl = liveEl;
            totalEl = totEl;
            ticker = setInterval(tick, 1000);
            refreshTotal();
        },
        onFilterChange(period) {
            refreshTotal();
        },
        fmt,
        fmtClock,
        totalForPeriod
    };
})();

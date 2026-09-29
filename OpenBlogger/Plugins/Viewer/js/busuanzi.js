/**
 * Viewer — 站点统计（不蒜子 busuanzi 后端）
 *
 * 全站浏览 / 本页阅读 / 独立访客 三项数据，全部按「本站域名 + 页面路径」
 * 独立统计，是你这个博客自己的真实数据，不与他人共库，也不需要注册账号。
 *
 * 对外接口（与模板保持一致）：
 *   Viewer.getGlobalCount()            → Promise<number>        全站浏览
 *   getVisitCount()                    → Promise<number>        本页阅读
 *   Viewer.getUniqueCount()            → Promise<{count:number}> 独立访客
 *
 * 如果统计服务被墙或超时，页面上的数字会退化为「—」，不会影响其它功能。
 */

var Viewer = Viewer || {};

(function () {
    var SRC = 'https://busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js';

    // 页面上的占位元素 → 不蒜子的数据元素
    var TARGETS = {
        'vGlobal':  'busuanzi_value_site_pv',   // 🌐 次全站浏览
        'vCounter': 'busuanzi_value_page_pv',   // 👁️ 次阅读（本页）
        'vUnique':  'busuanzi_value_site_uv'    // 👤 位访客
    };

    var TIMEOUT = 9000;
    var loaded = false;

    function loadService() {
        if (loaded) return;
        loaded = true;

        // 不蒜子脚本靠这几个 id 定位节点，所以先塞一组隐藏容器进页面
        var box = document.createElement('div');
        box.setAttribute('aria-hidden', 'true');
        box.style.cssText = 'position:absolute;left:-9999px;top:0;width:0;height:0;overflow:hidden';
        box.innerHTML =
            '<span id="busuanzi_container_site_pv"><span id="busuanzi_value_site_pv"></span></span>' +
            '<span id="busuanzi_container_page_pv"><span id="busuanzi_value_page_pv"></span></span>' +
            '<span id="busuanzi_container_site_uv"><span id="busuanzi_value_site_uv"></span></span>';
        document.body.appendChild(box);

        var s = document.createElement('script');
        s.async = true;
        s.src = SRC;
        s.onerror = function () { failAll(); };
        document.body.appendChild(s);
    }

    function readValue(targetId) {
        var el = document.getElementById(TARGETS[targetId]);
        if (!el) return null;
        var t = (el.textContent || '').replace(/[^\d]/g, '');
        if (!t) return null;
        var n = parseInt(t, 10);
        return isNaN(n) ? null : n;
    }

    function fail(el) { if (el) el.textContent = '—'; }

    function failAll() {
        Object.keys(TARGETS).forEach(function (id) { fail(document.getElementById(id)); });
    }

    /** 轮询直到拿到数值 */
    function waitFor(targetId) {
        return new Promise(function (resolve, reject) {
            var started = Date.now();
            (function tick() {
                var v = readValue(targetId);
                if (v !== null) return resolve(v);
                if (Date.now() - started > TIMEOUT) {
                    fail(document.getElementById(targetId));
                    return reject(new Error('统计服务超时'));
                }
                setTimeout(tick, 300);
            })();
        });
    }

    Viewer.getGlobalCount = function () { loadService(); return waitFor('vGlobal'); };

    Viewer.getUniqueCount = function () {
        loadService();
        return waitFor('vUnique').then(function (n) { return { count: n, isNew: false }; });
    };

    window.getVisitCount = function () { loadService(); return waitFor('vCounter'); };
})();

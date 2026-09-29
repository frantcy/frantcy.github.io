/**
 * Viewer — 独立访客计数器
 * 基于 localStorage 判重，首次访问才 +1，通过 TinyWebDB 持久化存储
 */

var Viewer = Viewer || {};

(function () {
    var API    = 'https://tinywebdb.appinventor.space/api';
    var USER   = (window.ViewerConfig && window.ViewerConfig.user) || 'aaaaa';
    var SECRET = (window.ViewerConfig && window.ViewerConfig.secret) || 'd1bdf09a';

    // 读取页面编号，实现多页面独立计数
    function getPageId() {
        var meta = document.querySelector('meta[name="x-viewer-page-id"]');
        return meta ? meta.getAttribute('content') : '';
    }
    var pid = getPageId();
    var TAG = 'unique_watch' + (pid ? '_' + pid : '');
    var STORAGE_KEY = 'viewer_visited' + (pid ? '_' + pid : '');

    function call(params) {
        var body = new URLSearchParams({ user: USER, secret: SECRET });
        Object.keys(params).forEach(function (k) { body.append(k, params[k]); });
        return fetch(API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body.toString()
        }).then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.text();
        }).then(function (t) {
            try { return JSON.parse(t); } catch (e) { return t; }
        });
    }

    /** 从 get 返回中提取值 */
    function extractVal(raw, tag) {
        var v = raw;
        if (Array.isArray(raw) && raw[0] === 'VALUE') { v = raw[2]; }
        else if (typeof raw === 'object' && raw !== null && raw[tag] !== undefined) { v = raw[tag]; }
        return v;
    }

    /**
     * 获取独立访客数
     * 首次访问（localStorage 无标记）→ +1 再返回
     * 回访（localStorage 有标记）→ 直接返回当前值
     * @returns {Promise<{count: number, isNew: boolean}>}
     */
    Viewer.getUniqueCount = function () {
        return call({ action: 'get', tag: TAG }).then(function (raw) {
            var v = extractVal(raw, TAG);
            var curNum = parseInt(v, 10);
            if (isNaN(curNum)) curNum = 0;

            var isNew = !localStorage.getItem(STORAGE_KEY);

            if (isNew) {
                localStorage.setItem(STORAGE_KEY, '1');
                curNum = curNum + 1;
                return call({ action: 'update', tag: TAG, value: String(curNum) }).then(function () {
                    return { count: curNum, isNew: true };
                });
            }

            return { count: curNum, isNew: false };
        });
    };
})();

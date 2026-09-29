/**
 * Viewer — 全站累计浏览量
 * 不区分页面，所有页面共享同一个计数器
 */

var Viewer = Viewer || {};

(function () {
    var API    = 'https://tinywebdb.appinventor.space/api';
    var USER   = (window.ViewerConfig && window.ViewerConfig.user) || 'aaaaa';
    var SECRET = (window.ViewerConfig && window.ViewerConfig.secret) || 'd1bdf09a';
    var TAG    = 'global_watch';  // 固定 tag，不跟页面编号

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

    /**
     * 获取全站累计浏览量
     * @returns {Promise<number>}
     */
    Viewer.getGlobalCount = function () {
        return call({ action: 'get', tag: TAG }).then(function (raw) {
            var v = raw;
            if (Array.isArray(raw) && raw[0] === 'VALUE') {
                v = raw[2];
            } else if (typeof raw === 'object' && raw !== null && raw[TAG] !== undefined) {
                v = raw[TAG];
            }
            var oldNum = parseInt(v, 10);
            var newNum = isNaN(oldNum) ? 1 : oldNum + 1;
            return call({ action: 'update', tag: TAG, value: String(newNum) }).then(function () {
                return newNum;
            });
        });
    };
})();

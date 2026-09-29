/**
 * Viewer — 评论系统
 * 基于 TinyWebDB 云数据库，每条评论存为一个独立 tag
 */

var Viewer = Viewer || {};

(function () {
    var API    = 'https://tinywebdb.appinventor.space/api';
    var USER   = (window.ViewerConfig && window.ViewerConfig.user) || 'aaaaa';
    var SECRET = (window.ViewerConfig && window.ViewerConfig.secret) || 'd1bdf09a';

    // 读取页面编号，实现多页面独立评论
    function getPageId() {
        var meta = document.querySelector('meta[name="x-viewer-page-id"]');
        return meta ? meta.getAttribute('content') : '';
    }
    var pid = getPageId();
    var PREFIX    = pid ? 'comment_' + pid + '_' : 'comment_';
    var COUNT_TAG = pid ? 'comment_count_' + pid : 'comment_count';

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
     * 获取评论总数
     * @returns {Promise<number>}
     */
    function getCommentCount() {
        return call({ action: 'get', tag: COUNT_TAG }).then(function (raw) {
            var v = extractVal(raw, COUNT_TAG);
            var n = parseInt(v, 10);
            return isNaN(n) ? 0 : n;
        });
    }

    /**
     * 加载所有评论
     * @returns {Promise<Array>}
     */
    Viewer.loadComments = function () {
        return getCommentCount().then(function (count) {
            if (count === 0) return [];
            var tasks = [];
            for (var i = 1; i <= count; i++) {
                tasks.push(call({ action: 'get', tag: PREFIX + i }));
            }
            return Promise.all(tasks).then(function (results) {
                return results.map(function (raw, idx) {
                    var v = extractVal(raw, PREFIX + (idx + 1));
                    if (!v) return null;
                    try {
                        return typeof v === 'string' ? JSON.parse(v) : v;
                    } catch (e) {
                        return null;
                    }
                }).filter(Boolean);
            });
        });
    };

    /**
     * 提交评论
     * @param {Object} comment - { name, email, content }
     * @returns {Promise<Object>} 完整评论对象（含时间）
     */
    Viewer.submitComment = function (comment) {
        return getCommentCount().then(function (count) {
            var newIdx = count + 1;
            var now = new Date();
            var full = {
                name:    comment.name    || '匿名',
                email:   comment.email   || '',
                content: comment.content || '',
                time:    now.toISOString()
            };
            var tag = PREFIX + newIdx;
            return call({ action: 'update', tag: tag, value: JSON.stringify(full) }).then(function () {
                return call({ action: 'update', tag: COUNT_TAG, value: String(newIdx) });
            }).then(function () {
                return full;
            });
        });
    };
})();

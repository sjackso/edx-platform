define(["js/models/xblock_info"],
    function(XBlockInfo) {
        var CustomSyncXBlockInfo = XBlockInfo.extend({
            sync: function(method, model, options) {
                var urlRoot = this.urlRoots[method];
                if (!urlRoot) {
                    urlRoot = this.urlRoot;
                }
                options.url = urlRoot + '/' + this.get('id');
                return XBlockInfo.prototype.sync.call(this, method, model, options);
            }
        });
        return CustomSyncXBlockInfo;
    });

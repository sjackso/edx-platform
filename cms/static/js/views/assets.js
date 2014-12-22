define(["jquery", "underscore", "gettext", "js/models/asset", "js/views/paging", "js/views/asset",
    "js/views/paging_header", "js/views/paging_footer", "js/utils/modal", "js/views/utils/view_utils",
    "js/views/feedback_notification", "jquery.fileupload-process", "jquery.fileupload-validate"],
    function($, _, gettext, AssetModel, PagingView, AssetView, PagingHeader, PagingFooter, ModalUtils, ViewUtils, NotificationView) {

        var CONVERSION_FACTOR_MBS_TO_BYTES = 1000 * 1000;

        var AssetsView = PagingView.extend({
            // takes AssetCollection as model

            events : {
                "click .column-sort-link": "onToggleColumn",
                "click .upload-button": "showUploadModal",
                "click .filterable-column .nav-item": "onFilterColumn",
                "click .filterable-column .column-filter-link": "toggleFilterColumn"
            },

            typeData: ['Images', 'Documents', 'Text'],

            allLabel: 'ALL',

            initialize : function(options) {
                options = options || {};

                PagingView.prototype.initialize.call(this);
                var collection = this.collection;
                this.template = this.loadTemplate("asset-library");
                this.listenTo(collection, 'destroy', this.handleDestroy);
                this.registerSortableColumn('js-asset-name-col', gettext('Name'), 'display_name', 'asc');
                this.registerSortableColumn('js-asset-date-col', gettext('Date Added'), 'date_added', 'desc');
                this.registerFilterableColumn('js-asset-type-col', gettext('Type'), 'asset_type');
                this.setInitialSortColumn('js-asset-date-col');
                this.setInitialFilterColumn('js-asset-type-col');
                ViewUtils.showLoadingIndicator();
                this.setPage(0);
                // set default file size for uploads via template var,
                // and default to static old value if none exists
                this.uploadChunkSizeInMBs = options.uploadChunkSizeInMBs || 10;
                this.maxFileSizeInMBs = options.maxFileSizeInMBs || 10;
                this.uploadChunkSizeInBytes = this.uploadChunkSizeInMBs * CONVERSION_FACTOR_MBS_TO_BYTES;
                this.maxFileSizeInBytes = this.maxFileSizeInMBs * CONVERSION_FACTOR_MBS_TO_BYTES;
                this.maxFileSizeRedirectUrl = options.maxFileSizeRedirectUrl || '';
                assetsView = this;
                // error message modal for large file uploads
                this.largeFileErrorMsg = null;
            },

            render: function() {
                // Wait until the content is loaded the first time to render
                return this;
            },

            afterRender: function(){
                // Bind events with html elements
                $('li a.upload-button').on('click', this.showUploadModal);
                $('.upload-modal .close-button').on('click', this.hideModal);
                $('.upload-modal .choose-file-button').on('click', this.showFileSelectionMenu);
                return this;
            },

            getTableBody: function() {
                var tableBody = this.tableBody;
                if (!tableBody) {
                    ViewUtils.hideLoadingIndicator();

                    // Create the table
                    this.$el.html(this.template({typeData: this.typeData}));
                    tableBody = this.$('#asset-table-body');
                    this.tableBody = tableBody;
                    this.pagingHeader = new PagingHeader({view: this, el: $('#asset-paging-header')});
                    this.pagingFooter = new PagingFooter({view: this, el: $('#asset-paging-footer')});
                    this.pagingHeader.render();
                    this.pagingFooter.render();

                    // Hide the contents until the collection has loaded the first time
                    this.$('.assets-library').hide();
                    this.$('.no-asset-content').hide();
                }
                return tableBody;
            },

            renderPageItems: function() {
                var self = this,
                assets = this.collection,
                hasAssets = this.collection.assetFilter != '' ? true: assets.length > 0,
                tableBody = this.getTableBody();
                tableBody.empty();
                if (hasAssets) {
                    assets.each(
                        function(asset) {
                            var view = new AssetView({model: asset});
                            tableBody.append(view.render().el);
                        }
                    );
                }
                self.$('.assets-library').toggle(hasAssets);
                self.$('.no-asset-content').toggle(!hasAssets);
                return this;
            },

            onError: function() {
                ViewUtils.hideLoadingIndicator();
            },

            handleDestroy: function(model) {
                this.collection.fetch({reset: true}); // reload the collection to get a fresh page full of items
                analytics.track('Deleted Asset', {
                    'course': course_location_analytics,
                    'id': model.get('url')
                });
            },

            addAsset: function (model) {
                // Switch the sort column back to the default (most recent date added) and show the first page
                // so that the new asset is shown at the top of the page.
                this.setInitialSortColumn('js-asset-date-col');
                this.setPage(0);

                analytics.track('Uploaded a File', {
                    'course': course_location_analytics,
                    'asset_url': model.get('url')
                });
            },

            onToggleColumn: function(event) {
                var columnName = event.target.id;
                this.toggleSortOrder(columnName);
            },

            onFilterColumn: function(event) {
                var columnName = event.target.id;
                this.openFilterColumn(columnName, event);
            },

            hideModal: function (event) {
                if (event) {
                    event.preventDefault();
                }
                $('.file-input').unbind('change.startUpload');
                ModalUtils.hideModal();
                if (assetsView.largeFileErrorMsg) {
                  assetsView.largeFileErrorMsg.hide();
                }
            },

            showUploadModal: function (event) {
                var self = assetsView;
                event.preventDefault();
                self.resetUploadModal();
                ModalUtils.showModal();
                $('.file-input').bind('change', self.startUpload);
                $('.upload-modal .file-chooser').fileupload({
                    dataType: 'json',
                    type: 'POST',
                    maxChunkSize: self.uploadChunkSizeInBytes,
                    autoUpload: true,
                    progressall: function(event, data) {
                        var percentComplete = parseInt((100 * data.loaded) / data.total, 10);
                        self.showUploadFeedback(event, percentComplete);
                    },
                    maxFileSize: self.maxFileSizeInBytes,
                    maxNumberofFiles: 100,
                    done: function(event, data) {
                        self.displayFinishedUpload(data.result);
                    },
                    processfail: function(event, data) {
                        var filename = data.files[data.index].name;
                        var error = gettext("File {filename} exceeds maximum size of {maxFileSizeInMBs} MB")
                                    .replace("{filename}", filename)
                                    .replace("{maxFileSizeInMBs}", self.maxFileSizeInMBs)
                        
                        // disable second part of message for any falsy value, 
                        // which can be null or an empty string
                        if(self.maxFileSizeRedirectUrl) {
                            var instructions = gettext("Please follow the instructions here to upload a file elsewhere and link to it: {maxFileSizeRedirectUrl}")
                                    .replace("{maxFileSizeRedirectUrl}", self.maxFileSizeRedirectUrl);
                            error = error + " " + instructions;
                        }

                        assetsView.largeFileErrorMsg = new NotificationView.Error({
                            "title": gettext("Your file could not be uploaded"),
                            "message": error
                        });
                        assetsView.largeFileErrorMsg.show();

                        assetsView.displayFailedUpload({
                            "msg": gettext("Max file size exceeded")
                        });
                    },
                    processdone: function(event, data) {
                        assetsView.largeFileErrorMsg = null;
                    }
                });
            },

            showFileSelectionMenu: function(event) {
                event.preventDefault();
                $('.file-input').click();
            },

            startUpload: function (event) {
                var file = event.target.value;
                if (!assetsView.largeFileErrorMsg) {
                    $('.upload-modal h1').text(gettext('Uploading'));
                    $('.upload-modal .file-name').html(file.substring(file.lastIndexOf("\\") + 1));
                    $('.upload-modal .choose-file-button').hide();
                    $('.upload-modal .progress-bar').removeClass('loaded').show();
                }
            },

            resetUploadModal: function () {
                // Reset modal so it no longer displays information about previously
                // completed uploads.
                var percentVal = '0%';
                $('.upload-modal .progress-fill').width(percentVal);
                $('.upload-modal .progress-fill').html(percentVal);
                $('.upload-modal .progress-bar').hide();

                $('.upload-modal .file-name').show();
                $('.upload-modal .file-name').html('');
                $('.upload-modal .choose-file-button').text(gettext('Choose File'));
                $('.upload-modal .embeddable-xml-input').val('');
                $('.upload-modal .embeddable').hide();

                assetsView.largeFileErrorMsg = null;
            },

            showUploadFeedback: function (event, percentComplete) {
                var percentVal = percentComplete + '%';
                $('.upload-modal .progress-fill').width(percentVal);
                $('.upload-modal .progress-fill').html(percentVal);
            },

            openFilterColumn: function(filterColumn, event) {
                var $this = $(event.currentTarget);
                this.toggleFilterColumnState($this, event);
            },

            toggleFilterColumnState: function(menu, event){
                var $subnav = menu.find('.wrapper-nav-sub');
                var $title = menu.find('.title');
                var titleText = $title.find('.type-filter');
                var assetfilter = $(event.currentTarget).data('assetfilter');
                if(assetfilter == this.allLabel){
                    titleText.text(titleText.data('alllabel'));
                }
                else{
                    titleText.text(assetfilter);
                }

                if ($subnav.hasClass('is-shown')) {
                    $subnav.removeClass('is-shown');
                    $title.removeClass('is-selected');
                } else {
                    $('.nav-dd .nav-item .title').removeClass('is-selected');
                    $('.nav-dd .nav-item .wrapper-nav-sub').removeClass('is-shown');
                    $title.addClass('is-selected');
                    $subnav.addClass('is-shown');
                }
                // if propagation is not stopped, the event will bubble up to the
                // body element, which will close the dropdown.
                event.stopPropagation();
            },

            toggleFilterColumn: function(event) {
                event.preventDefault();
                var collection = this.collection;
                if($(event.currentTarget).data('assetfilter') == this.allLabel){
                   collection.assetFilter = '';
                }
                else{
                    collection.assetFilter = $(event.currentTarget).data('assetfilter');
                }

                this.selectFilter('js-asset-type-col');
                this.closeFilterPopup(event);
            },

            closeFilterPopup: function(event){
                var $menu = $(event.currentTarget).parents('.nav-dd.nav-item');
                this.toggleFilterColumnState($menu, event);
            },

            displayFinishedUpload: function (resp) {
                var asset = resp.asset;

                $('.upload-modal h1').text(gettext('Upload New File'));
                $('.upload-modal .embeddable-xml-input').val(asset.portable_url).show();
                $('.upload-modal .embeddable').show();
                $('.upload-modal .file-name').hide();
                $('.upload-modal .progress-fill').html(resp.msg);
                $('.upload-modal .choose-file-button').text(gettext('Load Another File')).show();
                $('.upload-modal .progress-fill').width('100%');

                assetsView.addAsset(new AssetModel(asset));
            },

            displayFailedUpload: function (resp) {
                $('.upload-modal h1').text(gettext('Upload New File'));
                $('.upload-modal .embeddable-xml-input').hide();
                $('.upload-modal .embeddable').hide();
                $('.upload-modal .file-name').hide();
                $('.upload-modal .progress-fill').html(resp.msg);
                $('.upload-modal .choose-file-button').text(gettext('Load Another File')).show();
                $('.upload-modal .progress-fill').width('0%');
            }
        });

        return AssetsView;
    }); // end define();

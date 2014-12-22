;(function (define, undefined) {
'use strict';
define([
    'jquery', 'backbone', 'js/edxnotes/utils/template', 'js/edxnotes/utils/logger'
], function ($, Backbone, templateUtils, NotesLogger) {
    var NoteItemView = Backbone.View.extend({
        tagName: 'article',
        className: 'note',
        id: function () {
            return 'note-' + _.uniqueId();
        },
        events: {
            'click .note-excerpt-more-link': 'moreHandler',
            'click .reference-unit-link': 'unitLinkHandler',
        },

        initialize: function (options) {
            this.template = templateUtils.loadTemplate('note-item');
            this.logger = NotesLogger.getLogger('note_item', options.debug);
            this.listenTo(this.model, 'change:is_expanded', this.render);
        },

        render: function () {
            var context = this.getContext();
            this.$el.html(this.template(context));

            return this;
        },

        getContext: function () {
            return $.extend({
                message: this.model.getNoteText()
            }, this.model.toJSON());
        },

        toggleNote: function () {
            var value = !this.model.get('is_expanded');
            this.model.set('is_expanded', value);
        },

        moreHandler: function (event) {
            event.preventDefault();
            this.toggleNote();
        },

        unitLinkHandler: function (event) {
            this.logger.emit('edx.notes.went_to_unit', {
                'note_id': this.model.get('id'),
                'user': this.model.get('user'),
                'usage_id': this.model.get('usage_id')
            }, false);
        },

        remove: function () {
            this.logger.destroy();
            Backbone.View.prototype.remove.call(this);
            return this;
        }
    });

    return NoteItemView;
});
}).call(this, define || RequireJS.define);

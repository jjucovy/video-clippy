(function() {
    'use strict';

    // Assumes admin is mounted at /admin/. If the admin URL prefix changes,
    // update this path accordingly.
    var CHOICES_URL = '/admin/archive/customfield/choices-for-field/';

    function swapValueWidget(fieldSelect) {
        var fieldId = fieldSelect.value;
        var row = fieldSelect.closest('tr') || fieldSelect.closest('.form-row');
        if (!row) return;

        // Find the value widget in the same row
        var valueField = row.querySelector(
            'textarea[name$="-value"], select[name$="-value"], input[name$="-value"]'
        );
        if (!valueField) return;

        if (!fieldId) {
            replaceWithInput(valueField, '');
            return;
        }

        fetch(CHOICES_URL + fieldId + '/')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.field_type === 'choice' && data.choices && data.choices.length > 0) {
                    replaceWithSelect(valueField, data.choices);
                } else {
                    replaceWithInput(valueField, '');
                }
            })
            .catch(function() {
                replaceWithInput(valueField, '');
            });
    }

    function replaceWithSelect(element, choices) {
        var currentValue = element.value;

        var select = document.createElement('select');
        select.name = element.name;
        select.id = element.id;

        var emptyOpt = document.createElement('option');
        emptyOpt.value = '';
        emptyOpt.textContent = '---------';
        select.appendChild(emptyOpt);

        choices.forEach(function(choice) {
            var opt = document.createElement('option');
            opt.value = choice;
            opt.textContent = choice;
            if (currentValue === choice) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });

        element.parentNode.replaceChild(select, element);
    }

    function replaceWithInput(element, placeholder) {
        if (element.tagName === 'INPUT') return;

        var input = document.createElement('input');
        input.type = 'text';
        input.name = element.name;
        input.id = element.id;
        input.placeholder = placeholder || '';
        input.value = '';

        element.parentNode.replaceChild(input, element);
    }

    function initRow(row) {
        var fieldSelect = row.querySelector('select[name$="-field"]');
        if (!fieldSelect) return;
        if (fieldSelect.dataset.cfBound) return;
        fieldSelect.dataset.cfBound = '1';

        fieldSelect.addEventListener('change', function() {
            swapValueWidget(this);
        });

        // If a field is already selected (existing row), swap on load
        if (fieldSelect.value) {
            swapValueWidget(fieldSelect);
        }
    }

    function initAll() {
        var inlineGroups = document.querySelectorAll('.inline-group');
        inlineGroups.forEach(function(group) {
            group.querySelectorAll('tr, .form-row').forEach(initRow);

            // Watch for "Add another" rows
            var observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    mutation.addedNodes.forEach(function(node) {
                        if (node.nodeType === 1) {
                            if (node.matches && (node.matches('tr') || node.matches('.form-row'))) {
                                initRow(node);
                            }
                            node.querySelectorAll && node.querySelectorAll('tr, .form-row').forEach(initRow);
                        }
                    });
                });
            });
            observer.observe(group, { childList: true, subtree: true });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})();

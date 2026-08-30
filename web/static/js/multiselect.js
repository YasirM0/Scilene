// Compact multi-select filters (indexing/quartile/SINTA level/language) --
// the SECOND deliberate, narrow exception to this app's zero-custom-JS
// architecture, alongside the dark-mode toggle (see nav.html and
// docs/DESIGN_SYSTEM.md's "JavaScript exceptions" note for why both
// are considered legitimate rather than a slide back toward a JS app).
//
// Native <details>/<summary> (the zero-JS approach used before this)
// has two hard limitations no amount of CSS works around: there is no
// "click outside to close" behavior at all, and nesting a removable
// chip inside a clickable <summary> makes removing a chip ALSO toggle
// the dropdown open/closed as an unwanted side effect, because the
// click bubbles to the summary's native disclosure behavior. Both are
// exactly what a Streamlit st.multiselect-style control needs to get
// right, so this file exists.
//
// Everything is delegated off `document` rather than attached to
// individual elements, on purpose: the language filter card
// (components/language_filter_card.html) gets replaced wholesale by
// an HTMX out-of-band swap when the detected language changes
// (web/routers/interpreter.py), which would silently orphan any
// listeners attached directly to its old DOM nodes. Delegation means
// new markup works immediately with no re-initialization step.
//
// No chip HTML is ever generated here. components/multi_select_filter.html
// and components/language_filter_card.html render one chip PER OPTION
// up front (hidden unless that option starts selected) -- this file
// only ever toggles a chip's `hidden` attribute to match its
// checkbox, never builds markup, so translated labels/aria-labels
// never have to be duplicated in JS. The checkboxes remain the actual
// form state and HTMX live-filter trigger target (see
// multi_select_filter.html's "live-filter" class and pages/search.html's
// hx-trigger="change from:.live-filter") -- unchanged by any of this.
//
// #143 -- this file also owns showing/hiding the Quartile and SINTA
// Level controls based on what's checked in Preferred Indexing (see
// syncIndexGatedFilters() below and index_quality_language_filters.html's
// header comment for why a hidden control must also be cleared, not
// just hidden).

// Journal-card subject tags (components/journal_card.html) -- clicking
// one checks the matching Subject Category checkbox instead of making
// the user open the filter panel and find it themselves. Reuses the
// exact same checked+dispatch("change") mechanism as ms-chip-remove
// below so it drives the real live-filter/HTMX flow, not a parallel
// one -- the resulting search request and chip/dropdown state stay
// identical to checking that box by hand.
document.addEventListener("click", function (event) {
    var tag = event.target.closest(".subject-tag-chip");
    if (!tag) return;
    var category = tag.dataset.subjectCategory;
    if (!category) return;
    var checkbox = document.querySelector('input.live-filter[name="categories"][value="' + CSS.escape(category) + '"]');
    if (!checkbox || checkbox.checked) return;
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
});

document.addEventListener("click", function (event) {
    var chipRemove = event.target.closest(".ms-chip-remove");
    if (chipRemove) {
        // Handle removal first and stop here -- must never also reach
        // the control-box toggle below, which is exactly the
        // <summary>-nesting bug this file replaces.
        event.preventDefault();
        event.stopPropagation();
        var checkbox = document.getElementById(chipRemove.dataset.target);
        if (checkbox) {
            checkbox.checked = false;
            checkbox.dispatchEvent(new Event("change", { bubbles: true }));
        }
        return;
    }

    var control = event.target.closest(".ms-control");
    if (control) {
        var wrapper = control.closest("[data-multiselect]");
        var wasOpen = wrapper.classList.contains("ms-open");
        closeAllMultiselects();
        if (!wasOpen) {
            openMultiselect(wrapper);
        }
        return;
    }

    if (event.target.closest(".ms-dropdown")) {
        // Clicking a checkbox/label inside the open dropdown must not
        // close it -- picking several options in sequence is the
        // whole point of a multi-select.
        return;
    }

    // Click landed outside every multiselect control -- this is the
    // "click outside to close" native <details> can't do.
    closeAllMultiselects();
});

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
        closeAllMultiselects();
        return;
    }
    // The search box (see filterMultiselectOptions() below) sits inside
    // the same <form> as the search page's own submit button -- Enter
    // in a text input submits the nearest form by default, which would
    // fire a real search mid-typing instead of just narrowing the
    // dropdown's own option list.
    if (event.key === "Enter" && event.target.classList.contains("ms-search")) {
        event.preventDefault();
        return;
    }
    // <div class="ms-control" tabindex="0"> has no native Enter/Space
    // activation the way a real <button> would.
    if ((event.key === "Enter" || event.key === " ") && event.target.classList.contains("ms-control")) {
        event.preventDefault();
        var wrapper = event.target.closest("[data-multiselect]");
        var wasOpen = wrapper.classList.contains("ms-open");
        closeAllMultiselects();
        if (!wasOpen) {
            openMultiselect(wrapper);
        }
    }
});

// Live-filters a searchable dropdown's own option rows by substring
// (case-insensitive) as the user types -- the categories list (44
// subject names) is the one long enough that scanning it manually was
// the actual complaint; short lists don't render a .ms-search box at
// all (see multi_select_filter.html's `searchable` param) so this
// never runs for them.
document.addEventListener("input", function (event) {
    var search = event.target.closest(".ms-search");
    if (!search) return;
    var wrapper = search.closest("[data-multiselect]");
    if (!wrapper) return;
    filterMultiselectOptions(wrapper, search.value);
});

function filterMultiselectOptions(wrapper, query) {
    var q = query.trim().toLowerCase();
    var anyVisible = false;
    wrapper.querySelectorAll(".ms-dropdown label").forEach(function (label) {
        var matches = !q || label.textContent.trim().toLowerCase().indexOf(q) !== -1;
        label.hidden = !matches;
        anyVisible = anyVisible || matches;
    });
    var noMatches = wrapper.querySelector(".ms-no-matches");
    if (noMatches) noMatches.hidden = anyVisible;
}

// Keeps each option's pre-rendered chip in sync with its checkbox --
// covers both directions: checking a box in the dropdown reveals its
// chip, and the ms-chip-remove button above unchecks the box and
// re-dispatches "change", which lands right back here.
document.addEventListener("change", function (event) {
    var checkbox = event.target.closest(".live-filter");
    if (!checkbox) return;
    syncChipForCheckbox(checkbox);
});

// #143 -- a SEPARATE, CAPTURE-phase listener (the `true` third
// argument), not just another case inside the bubble-phase one above.
// Capture runs top-down (document -> ... -> target) BEFORE the same
// event's bubble phase reaches the <form>, where HTMX's own
// `hx-trigger="change from:.live-filter"` reads the form's current
// values. Clearing a now-irrelevant quartile/SINTA-level selection
// HERE means that single read already sees the corrected state --
// one accurate search request. Doing this in the bubble-phase
// listener instead (tried first) worked too, but only by dispatching
// a fresh "change" per cleared checkbox -- each one racing HTMX's
// listener again and firing its own real, immediately-superseded
// request, so unchecking one indexing source could fire 3-4 requests
// in a burst instead of one.
document.addEventListener("change", function (event) {
    var checkbox = event.target.closest('input.live-filter[name="indexing"]');
    if (!checkbox) return;
    syncIndexGatedFilters();
}, true);

function syncChipForCheckbox(checkbox) {
    var wrapper = checkbox.closest("[data-multiselect]");
    if (!wrapper) return;

    var chip = wrapper.querySelector('.ms-chip[data-for="' + checkbox.id + '"]');
    if (chip) chip.hidden = !checkbox.checked;

    var anySelected = !!wrapper.querySelector(".ms-chip:not([hidden])");
    var placeholder = wrapper.querySelector(".ms-placeholder");
    if (placeholder) placeholder.hidden = anySelected;
}

// #143 -- hides components/index_quality_language_filters.html's
// quartile/SINTA wrappers unless their required indexing source is
// currently checked, AND clears (not just hides) that group's own
// checkboxes the moment it's hidden -- a hidden control must never
// keep silently narrowing results the user can no longer see or
// adjust. Runs once on initial load/every HTMX swap (so an OOB reset
// like Clear Search re-evaluates against its own fresh defaults) plus
// reactively on every indexing checkbox change (see the capture-phase
// listener above -- no "change" event is dispatched for the
// checkboxes cleared here, on purpose; see that listener's comment).
function syncIndexGatedFilters() {
    var checkedIndexing = Array.prototype.map.call(
        document.querySelectorAll('input.live-filter[name="indexing"]:checked'),
        function (checkbox) { return checkbox.value; }
    );

    document.querySelectorAll("[data-requires-indexing]").forEach(function (gated) {
        var required = gated.dataset.requiresIndexing.split(",");
        var shouldShow = required.some(function (value) { return checkedIndexing.indexOf(value) !== -1; });

        gated.hidden = !shouldShow;
        if (!shouldShow) {
            gated.querySelectorAll(".live-filter:checked").forEach(function (checkbox) {
                checkbox.checked = false;
                syncChipForCheckbox(checkbox);
            });
        }
    });
}

document.addEventListener("DOMContentLoaded", syncIndexGatedFilters);
document.body.addEventListener("htmx:afterSwap", syncIndexGatedFilters);

function openMultiselect(wrapper) {
    wrapper.classList.add("ms-open");
    var control = wrapper.querySelector(".ms-control");
    var dropdown = wrapper.querySelector(".ms-dropdown");
    if (control) control.setAttribute("aria-expanded", "true");
    if (dropdown) dropdown.hidden = false;

    // Always reopen with a blank search and every option visible --
    // a stale filter from the last time this dropdown was open would
    // otherwise silently hide options the user never meant to exclude.
    var search = wrapper.querySelector(".ms-search");
    if (search) {
        search.value = "";
        filterMultiselectOptions(wrapper, "");
        search.focus();
    }
}

function closeMultiselect(wrapper) {
    wrapper.classList.remove("ms-open");
    var control = wrapper.querySelector(".ms-control");
    var dropdown = wrapper.querySelector(".ms-dropdown");
    if (control) control.setAttribute("aria-expanded", "false");
    if (dropdown) dropdown.hidden = true;
}

function closeAllMultiselects() {
    document.querySelectorAll("[data-multiselect].ms-open").forEach(closeMultiselect);
}

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

// Keeps each option's pre-rendered chip in sync with its checkbox --
// covers both directions: checking a box in the dropdown reveals its
// chip, and the ms-chip-remove button above unchecks the box and
// re-dispatches "change", which lands right back here.
document.addEventListener("change", function (event) {
    var checkbox = event.target.closest(".live-filter");
    if (!checkbox) return;
    var wrapper = checkbox.closest("[data-multiselect]");
    if (!wrapper) return;

    var chip = wrapper.querySelector('.ms-chip[data-for="' + checkbox.id + '"]');
    if (chip) chip.hidden = !checkbox.checked;

    var anySelected = !!wrapper.querySelector(".ms-chip:not([hidden])");
    var placeholder = wrapper.querySelector(".ms-placeholder");
    if (placeholder) placeholder.hidden = anySelected;
});

function openMultiselect(wrapper) {
    wrapper.classList.add("ms-open");
    var control = wrapper.querySelector(".ms-control");
    var dropdown = wrapper.querySelector(".ms-dropdown");
    if (control) control.setAttribute("aria-expanded", "true");
    if (dropdown) dropdown.hidden = false;
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

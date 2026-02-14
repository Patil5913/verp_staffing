document.addEventListener('DOMContentLoaded', function () {

    // // Disable Right-Click (Context Menu)
    // document.addEventListener('contextmenu', event => event.preventDefault());

    // // Disable Copy, Cut, and Paste Events
    // ['copy', 'cut', 'paste'].forEach(event => {
    //     document.addEventListener(event, e => {
    //         e.preventDefault();
    //         frappe.show_alert({
    //             message: __("Copy/Paste is disabled in this application."),
    //             indicator: 'orange'
    //         });
    //     });
    // });


    // document.addEventListener('keyup', function (e) {

    //     // Check for the PrintScreen key (standard name or legacy code 44)
    //     if (e.code === 'PrintScreen' || e.keyCode === 44) {
    //         e.preventDefault()
    //         // Immediately clear the clipboard
    //         navigator.clipboard.writeText("").then(() => {
    //             frappe.show_alert({
    //                 message: __('Screenshots are restricted. Clipboard cleared.'),
    //                 indicator: 'red'
    //             });
    //         });
    //     }
    // });

    // // Disable Keyboard Shortcuts (Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+U, F12)
    // document.addEventListener('keydown', function (e) {
    //     if (
    //         (e.ctrlKey && ['c', 'v', 'x', 'u', 'p'].includes(e.key.toLowerCase())) ||
    //         e.key === 'F12'
    //     ) {
    //         e.preventDefault();
    //     }

    //     if ((e.altKey) && e.key == "printscreen") {
    //         e.preventDefault();
    //         frappe.show_alert({ message: __('Screen capture shortcut disabled'), indicator: 'red' });
    //     }
    //     // Disable Win + Shift + S (Snipping Tool) or Cmd + Shift + 4 (Mac)
    //     if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'S' || e.key === '4')) {
    //         e.preventDefault();
    //         frappe.show_alert({ message: __('Screen capture shortcut disabled'), indicator: 'red' });
    //     }
    // });
});

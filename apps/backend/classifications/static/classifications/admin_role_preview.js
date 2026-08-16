(function () {
  "use strict";

  function updateRolePreview() {
    var submitter = document.getElementById("id_submitted_by");
    var role = document.getElementById("id_submitted_role");
    var weight = document.getElementById("id_submitted_base_weight");
    if (!submitter || !role || !weight) {
      return;
    }

    var mapAttr = submitter.getAttribute("data-role-map");
    if (!mapAttr) {
      return;
    }

    var map = JSON.parse(mapAttr);
    var selected = submitter.value;
    var data = map[selected];
    if (!data) {
      return;
    }

    role.value = data.role;
    weight.value = data.weight;
  }

  document.addEventListener("DOMContentLoaded", updateRolePreview);

  var submitter = document.getElementById("id_submitted_by");
  if (submitter) {
    submitter.addEventListener("change", updateRolePreview);
  }
})();

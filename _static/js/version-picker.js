function toggleVersionDropdown() {
  const dropdown = document.getElementById("version-dropdown");
  const arrow = document.querySelector(".dropdown-arrow");
  const isVisible = dropdown.style.display === "block";

  dropdown.style.display = isVisible ? "none" : "block";
  arrow.style.transform = isVisible ? "rotate(0deg)" : "rotate(180deg)";
}

// Close dropdown when clicking outside
document.addEventListener("click", function (event) {
  if (!event.target.closest(".version-dropdown")) {
    document.getElementById("version-dropdown").style.display = "none";
    document.querySelector(".dropdown-arrow").style.transform = "rotate(0deg)";
  }
});

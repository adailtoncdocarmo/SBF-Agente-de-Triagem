// Interações do cabeçalho: alterna o menu mobile e os submenus em acordeão.
// No desktop os submenus abrem por :hover (puro CSS); este script cobre o
// comportamento mobile, onde o botão hambúrguer abre o menu e cada botão de
// submenu expande/recolhe seu dropdown girando a seta.
(function () {
  var toggler = document.querySelector('.Header_toggler__mJIAI');
  var menu = document.querySelector('.Header_menu__list__dNAR2');
  if (toggler && menu) {
    toggler.addEventListener('click', function () {
      menu.classList.toggle('Header_menu__open__ayv6Q');
    });
  }
  document.querySelectorAll('.Submenu_submenu__toggler__9a_x_').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var dropdown = btn.nextElementSibling;
      var arrow = btn.querySelector('.Submenu_submenu__arrow__QzBQ_');
      if (dropdown) dropdown.classList.toggle('Submenu_dropdown--open__803r9');
      if (arrow) arrow.classList.toggle('Submenu_submenu__arrow--up__BTFv1');
    });
  });
})();

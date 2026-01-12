console.log("Mayacorp System Carregado com Sucesso!");

// Exemplo: Se quiser fechar alertas automaticamente depois
setTimeout(function() {
    let alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        alert.style.display = 'none';
    });
}, 5000);

const mayaModal = {
  el: document.getElementById('maya-modal'),

  open({ title, subtitle, url }) {
    document.getElementById('modal-title').innerText = title;
    document.getElementById('modal-subtitle').innerText = subtitle || '';

    fetch(url)
      .then(res => res.text())
      .then(html => {
        document.getElementById('modal-content').innerHTML = html;
        this.el.showModal();
      });
  },

  close() {
    this.el.close();
    document.getElementById('modal-content').innerHTML = '';
  }
};

<script>
function openCheckinModal(data) {
  const modal = document.getElementById('modal_checkin')

  document.getElementById('modalAluno').innerText = data.aluno
  document.getElementById('modalData').innerText = data.data
  document.getElementById('modalOcupacao').innerText = `Ocupação: ${data.ocupacao}`

  const icon = document.getElementById('modalIcon')
  icon.style.backgroundColor = data.cor + '20'
  icon.style.color = data.cor

  const form = document.getElementById('checkinForm')
  form.action = data.action
  form.reset()

  modal.showModal()
}
</script>
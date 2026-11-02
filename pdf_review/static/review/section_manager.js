import { jsonRequest } from './thread_api.js';
const manager=document.getElementById('section-manager');
const status=document.getElementById('section-management-status');
async function save(url,method,payload) {
  try { await jsonRequest(url,{method,body:JSON.stringify(payload)}); location.reload(); }
  catch(error) { status.textContent=error.message; }
}
document.getElementById('section-add').addEventListener('submit',event=>{
  event.preventDefault(); const values=Object.fromEntries(new FormData(event.target));
  save(`/api/documents/${manager.dataset.documentId}/sections`,'POST',values);
});
manager.querySelectorAll('.section-edit').forEach(form=>form.addEventListener('submit',event=>{
  event.preventDefault(); const values=Object.fromEntries(new FormData(form)); values.position=Number(values.position);
  save(`/api/sections/${form.dataset.sectionId}`,'PATCH',values);
}));
manager.querySelectorAll('[data-archive]').forEach(button=>button.addEventListener('click',()=>{
  if (confirm('Delete this section? Historical placements and feedback will be retained.')) save(`/api/sections/${button.dataset.archive}`,'PATCH',{archive:true});
}));

import json, tempfile, unittest, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from orchestrator import initialize_task,classify_and_route,mark_plan_ready,mark_architecture_ready,begin_implementation,OrchestratorError
from plan_store import save_plan
from architect_store import save_architecture

def plan(tid):
 return {"schema_version":"2.0.0","task_id":tid,"goal":"refactor architecture","in_scope":[],"out_of_scope":[],"constraints":[],"assumptions":[],"acceptance_criteria":["safe"],"risk_level":"HIGH","risk_notes":[],"release_constraints":[],"work_items":[{"id":"W1","objective":"build","owner_role":"BUILDER","scope_hints":[],"dependencies":[],"verification":["tests"],"status":"PENDING"}]}
def arch(tid,human=False):
 return {"schema_version":"1.0.0","task_id":tid,"status":"READY","human_precheck_required":human,"production_code_edits":False,"decision":{"summary":"Preserve boundaries","drivers":[],"decisions":[],"interfaces":[],"constraints":[],"risks":[],"builder_guidance":[],"verification_implications":[]}}
class C1(unittest.TestCase):
 def setUp(self): self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name)
 def tearDown(self): self.t.cleanup()
 def test_simple_bypasses_architect(self):
  initialize_task(self.root,"Fix typo in README","typo"); s=classify_and_route(self.root); self.assertFalse(s['classification']['architect_required']); self.assertEqual(s['lifecycle']['current_state'],'IMPLEMENTING')
 def test_complex_requires_architect_before_builder(self):
  s=initialize_task(self.root,"Refactor architecture across multiple services","arch"); s=classify_and_route(self.root,estimated_components=3); save_plan(self.root,plan(s['identity']['id'])); s=mark_plan_ready(self.root); self.assertIn('ARCHITECT',s['roles']['active'])
  with self.assertRaises(OrchestratorError): begin_implementation(self.root)
  save_architecture(self.root,arch(s['identity']['id']),s['identity']['id']); s=mark_architecture_ready(self.root); self.assertIn('ARCHITECT',s['roles']['completed']); self.assertEqual(begin_implementation(self.root)['lifecycle']['current_state'],'IMPLEMENTING')
 def test_architect_human_precheck(self):
  s=initialize_task(self.root,"Refactor architecture across multiple services","arch"); s=classify_and_route(self.root,estimated_components=3); save_plan(self.root,plan(s['identity']['id'])); mark_plan_ready(self.root); save_architecture(self.root,arch(s['identity']['id'],True),s['identity']['id']); self.assertEqual(mark_architecture_ready(self.root)['lifecycle']['current_state'],'HUMAN_DECISION')
if __name__=='__main__': unittest.main()

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_forge import fixture
from forge.core import GEX_REV
from forge.probe import probe_plan, execute_probe


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.game=self.root/'game';self.game.mkdir();self.exe=fixture(self.game/'game.exe')
        self.gex=self.root/'gex';self.dist=self.root/'dist';self.prefix=self.root/'prefix'
        for f in [self.gex/'wine/run.sh',self.dist/'lib/wine/x86_64-unix/wine',self.prefix/'system.reg']:
            f.parent.mkdir(parents=True,exist_ok=True);f.touch()
    def tearDown(self):self.tmp.cleanup()
    def plan(self,**kwargs):
        return probe_plan(self.gex,self.exe,self.dist,self.prefix,self.root/'units',self.root/'probe',**kwargs)
    def test_dry_run(self):
        with patch('forge.probe.subprocess.run') as run:
            p=self.plan(build_units=True);run.assert_not_called()
        self.assertIn('--build-units',p['argv']);self.assertEqual(p['argv'][-1],str(self.exe))
        self.assertFalse((self.root/'probe').exists())
    def test_architecture_mismatch(self):
        with self.assertRaisesRegex(ValueError,'architecture'):self.plan(arch='x86')
    def test_timeout_limit(self):
        with self.assertRaisesRegex(ValueError,'timeout'):self.plan(seconds=10000)
    def test_prevent_recursive_bundle(self):
        with self.assertRaisesRegex(ValueError,'outside the game'):
            probe_plan(self.gex,self.exe,self.dist,self.prefix,self.root/'units',self.game/'output')
    def test_missing_prefix(self):
        (self.prefix/'system.reg').unlink()
        with self.assertRaisesRegex(ValueError,'Missing prerequisite'):self.plan()
    def test_probe_orchestration(self):
        p=self.plan()
        with patch('forge.probe.subprocess.check_output',side_effect=[GEX_REV+'\n','']),patch('forge.probe.subprocess.run') as run:
            run.return_value.returncode=0
            result=execute_probe(p)
        self.assertEqual(result['status'],'probe-finished-not-gameplay-validated')
        self.assertTrue((self.root/'probe/probe.log').is_file())
        self.assertEqual(run.call_args.kwargs['env']['WINE32_PAGE_DIR'],str(self.root/'probe/page'))
    def test_probe_failure_recorded(self):
        p=self.plan()
        with patch('forge.probe.subprocess.check_output',side_effect=[GEX_REV+'\n','']),patch('forge.probe.subprocess.run') as run:
            run.return_value.returncode=9
            with self.assertRaisesRegex(ValueError,'probe failed'):execute_probe(p)
        self.assertEqual(json.loads((self.root/'probe/probe-status.json').read_text())['returncode'],9)
    def test_dirty_source_not_executed(self):
        p=self.plan()
        with patch('forge.probe.subprocess.check_output',side_effect=[GEX_REV+'\n',' M wine/run.sh']),patch('forge.probe.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError,'clean, pinned'):execute_probe(p)
            run.assert_not_called()
    def test_local_bench_contract(self):
        script=Path(__file__).resolve().parent.parent/'scripts/local-bench.sh'
        r=subprocess.run(['bash',str(script),'-s',str(self.root),'--','printf','%s','space ; $literal'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0);self.assertEqual(r.stdout,'space ; $literal')
    def test_local_bench_preserves_exit(self):
        script=Path(__file__).resolve().parent.parent/'scripts/local-bench.sh'
        r=subprocess.run(['bash',str(script),'--','bash','-c','exit 7'])
        self.assertEqual(r.returncode,7)

if __name__=='__main__':unittest.main()

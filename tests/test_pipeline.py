import copy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import tempfile
import json
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from scout import eligible, observation_delta
from render import validate, render


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026,11,17,tzinfo=timezone.utc)
        self.config = {'lookback_hours':24,'duration_under_seconds':60,'minimum_views_exclusive':10000}
        self.row = {'published':(self.now-timedelta(hours=1)).isoformat(),'duration_seconds':59,'views':10001}

    def test_strict_view_and_duration_boundaries(self):
        self.assertFalse(eligible(self.row,self.now,self.config)[0])
        for update in ({'views':10000},{'duration_seconds':60},{'duration_seconds':None},{'views':True}):
            self.assertTrue(eligible(dict(self.row,**update),self.now,self.config)[0])

    def test_old_and_future_video_rejected(self):
        for hours in (25,-1):
            row=dict(self.row,published=(self.now-timedelta(hours=hours)).isoformat())
            self.assertIn('outside_discovery_window',eligible(row,self.now,self.config)[0])

    def test_release_default_seven_day_boundary(self):
        config=json.loads((Path(__file__).resolve().parents[1]/'sources.json').read_text())
        self.assertEqual(config['lookback_hours'],168)
        for age, accepted in ((24,True),(167,True),(168,True),(168.01,False)):
            row=dict(self.row,published=(self.now-timedelta(hours=age)).isoformat())
            self.assertEqual(not eligible(row,self.now,config)[0],accepted)

    def test_growth_needs_baseline_and_sufficient_interval(self):
        self.assertIsNone(observation_delta(None,self.now,10000))
        delta=observation_delta(((self.now-timedelta(minutes=10)).isoformat(),100),self.now,90)
        self.assertTrue(delta['negative_change'])
        self.assertIsNone(delta['views_per_hour'])
        delta=observation_delta(((self.now-timedelta(hours=2)).isoformat(),100),self.now,200)
        self.assertEqual(delta['views_per_hour'],50)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.scan={'run_id':'sample','selected_ids':['vid'],'rules':{'minimum_views_exclusive':10000,'duration_under_seconds':60},
                   'videos':[{'id':'vid','url':'https://www.youtube.com/watch?v=vid','views':12000,'duration_seconds':20}]}
        self.item={'video_id':'vid','source_url':self.scan['videos'][0]['url'],'review_status':'reviewed',
                   'review_method':'full video frames','hook':'observed hook','mechanism_hypothesis':'hypothesis',
                   'limits':'views not sales','evidence':[{'at_seconds':0,'observation':'a product'}],
                   'adaptation':{'merchant':'shop','concept':'new demo','format':'9:16','cta':'visit product','assets':['product'],'qc':['check product'],'duration_seconds':10},
                   'shots':[{'start':0,'end':3,'visual':'show','copy':'look','audio':'tap'},{'start':3,'end':10,'visual':'finish','copy':'visit','audio':'hold'}]}
        self.analysis={'run_id':'sample','items':[self.item]}

    def test_all_selected_videos_require_outcome(self):
        with self.assertRaises(ValueError):validate(self.scan,{'run_id':'sample','items':[]})

    def test_temporal_window_cannot_be_silently_bypassed(self):
        scan=copy.deepcopy(self.scan);scan['selected_ids']=[]
        with self.assertRaises(ValueError):validate(scan,self.analysis)
        a=copy.deepcopy(self.analysis);a['items'][0]['historical_demo']=True
        validate(scan,a)

    def test_source_swap_and_timeline_gap_rejected(self):
        a=copy.deepcopy(self.analysis);a['items'][0]['source_url']='https://example.com'
        with self.assertRaises(ValueError):validate(self.scan,a)
        a=copy.deepcopy(self.analysis);a['items'][0]['shots'][1]['start']=4
        with self.assertRaises(ValueError):validate(self.scan,a)

    def test_unavailable_video_cannot_have_invented_analysis(self):
        a={'run_id':'sample','items':[{'video_id':'vid','source_url':self.item['source_url'],'review_status':'unavailable','reason':'no playback'}]}
        validate(self.scan,a)
        a['items'][0]['hook']='invented'
        with self.assertRaises(ValueError):validate(self.scan,a)

    def test_empty_day_produces_an_honest_report(self):
        scan=dict(self.scan,selected_ids=[],videos=[],status='no_qualifying_videos',timezone='Asia/Shanghai',
                  completed_at='2026-11-16T17:00:00+00:00',sources=[],limitations=['limited sample'],
                  coverage={'readable_sources':0,'total_sources':0,'videos_observed':0,'qualifying_videos':0})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'scan.json').write_text(json.dumps(scan));(p/'analysis.json').write_text(json.dumps({'run_id':'sample','items':[]}))
            render(p/'scan.json',p/'analysis.json',p/'report')
            text=(p/'report/report.md').read_text()
            self.assertIn('没有符合条件',text)
            self.assertNotIn('## 1.',text)
            self.assertNotIn('LOCAL DEMO',(p/'report/index.html').read_text())


if __name__=='__main__':unittest.main()

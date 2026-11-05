"""Synthetic contracts only. No official API success or licence is fabricated."""
import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser
from src import collector as c
from src.engine import execute
from src.news_discovery import (Batch, Transport, discover, endpoint_allowed, parse,
                                permissions, record_allowed)
from src.visibility import PublicationGate
from test_collector import AT, feed
from test_discovery_v03 import source


def publishers():
    return [source(id=sid, name='Fixture issuer '+sid, url='https://feeds.example.org/'+sid,
                   article_domains=[sid+'.example.org'],
                   coverage={'publisher_id': sid, 'publisher_jurisdiction': 'KR', 'media_type': 'public'})
            for sid in ('one', 'two')]


def provider(pid='test_route'):
    return {'id': pid, 'enabled': True, 'record_type': 'news', 'endpoint': 'https://api.example.org/list',
            'endpoint_hosts': ['api.example.org'], 'endpoint_verified': True,
            'endpoint_evidence_url': 'https://api.example.org/fixture-contract-only',
            'adapter': 'json_rows', 'response': {'contract_verified': True, 'rows_path': ['items'],
                'fields': {k: k for k in ('title', 'link', 'published', 'publisher_code', 'official_id')}},
            'capabilities': {k: {'status': 'approved', 'basis': 'isolated test grant, not a real licence',
                'evidence_url': 'https://example.org/fixture', 'verified_at': AT.isoformat(),
                **({'retention': 'permanent_metadata'} if k=='store' else {})}
                for k in ('access', 'process', 'store', 'publish')},
            'publishers': {sid: {'source_id': sid, 'publisher_id': sid, 'verified': True,
                'evidence_url': 'https://example.org/fixture-issuer', 'article_domains': [sid+'.example.org']}
                for sid in ('one', 'two')}, 'queries': [{}], 'interval_seconds': 7200,
            'max_calls_per_run': 1}


def item(sid='one', url=None, official='release1', **extra):
    return {'title': '한국 관광산업 지원 정책 발표', 'link': url or 'https://'+sid+'.example.org/a',
            'published': AT.isoformat(), 'publisher_code': sid, 'official_id': official, **extra}


def payload(*rows):
    return json.dumps({'items': rows}, ensure_ascii=False).encode()


class DiscoveryTests(unittest.TestCase):
    def test_four_capabilities_are_independent_and_missing_is_not_approval(self):
        p=provider();self.assertEqual(permissions(p)['state'], 'publishable')
        for key in ('access', 'process'):
            q=copy.deepcopy(p);q['capabilities'][key]['status']='review'
            self.assertEqual(permissions(q)['state'], 'blocked')
        p['capabilities']['publish']['status']='review'
        self.assertEqual(permissions(p)['state'], 'manual_review')
        p['capabilities']['store']['status']='review'
        self.assertEqual(permissions(p)['state'], 'discovery_only')
        p=provider();p['capabilities']['store']['retention']='24_hours'
        self.assertEqual(permissions(p)['state'], 'discovery_only')
        p=provider();del p['capabilities']['process']['evidence_url']
        self.assertEqual(permissions(p)['state'], 'blocked')

    def test_blocked_and_unverified_endpoint_make_no_calls(self):
        for change in [lambda p:p.update(enabled=False),
                       lambda p:p['capabilities']['access'].update(status='review'),
                       lambda p:p.update(endpoint_verified=False),
                       lambda p:p.update(endpoint='http://api.example.org/list')]:
            p=provider();change(p)
            with patch('src.news_discovery.Transport.__call__') as load:
                b=discover([p],publishers(),AT);load.assert_not_called();self.assertFalse(b.by_source)

    def test_discovery_only_and_review_have_no_title_url_or_ids_in_durable_output(self):
        for status in ('discovery_only','manual_review'):
            p=provider();p['capabilities']['publish']['status']='review'
            if status=='discovery_only':p['capabilities']['store']['status']='review'
            b=discover([p],publishers(),AT,loader=lambda *_:payload(item()))
            self.assertEqual(b.metrics[p['id']]['state'],status)
            self.assertEqual(b.by_source,{})
            serialized=json.dumps({'metrics':b.metrics,'cursors':b.cursors})
            for secret in [item()['title'],item()['link'],'release1']:
                self.assertNotIn(secret,serialized)
            self.assertEqual(b.metrics[p['id']]['unpublishable_candidate_metadata_persisted'],0)

    def test_statistics_contract_cannot_become_news(self):
        p=provider();p['record_type']='statistical_release'
        with patch('src.news_discovery.Transport.__call__') as load:
            b=discover([p],publishers(),AT)
            load.assert_not_called()
            self.assertEqual(b.metrics[p['id']]['error_kind'],'news_contract_not_verified')
            self.assertFalse(b.by_source)

    def test_two_issuers_share_a_route_but_not_a_source_identity(self):
        p=provider();b=discover([p],publishers(),AT,loader=lambda *_:payload(item(),item('two')))
        self.assertEqual(set(b.by_source),{'one','two'})
        self.assertEqual(b.metrics[p['id']]['verified_publishers'],['one','two'])
        for sid,rows in b.by_source.items():
            self.assertEqual(rows[0]['discovery_origin']['publisher_id'],sid)
            self.assertEqual(rows[0]['discovery_origin']['provider_id'],p['id'])

    def test_missing_issuer_and_relay_and_suffix_hosts_cannot_publish(self):
        for change in [{'publisher_code':None},{'publisher_code':'UNKNOWN'},
                       {'link':'https://search.example.org/relay'},
                       {'link':'https://one.example.org.evil/a'},
                       {'link':'https://u@one.example.org/a'},{'link':'https://one.example.org/a?serviceKey=not-a-credential-fixture'}]:
            p=provider();b=discover([p],publishers(),AT,loader=lambda *_:payload(item(**change)))
            self.assertEqual(b.by_source,{})
            self.assertEqual(b.metrics[p['id']]['attribution_holds'],1)

    def test_url_and_same_namespace_official_id_duplicates_across_routes(self):
        p,q=provider('p'),provider('q');p['official_id_namespace']=q['official_id_namespace']='fixture_common_official_id'
        def load(p,_):return payload(item(url='https://one.example.org/'+p['id']))
        b=discover([p,q],publishers(),AT,loader=load)
        self.assertEqual(sum(len(v) for v in b.by_source.values()),1)
        self.assertEqual(b.metrics['q']['duplicates'],1)
        # Distinct APIs can legitimately reuse the same numeric identifier.
        p.pop('official_id_namespace');q.pop('official_id_namespace')
        b=discover([p,q],publishers(),AT,loader=load)
        self.assertEqual(sum(len(v) for v in b.by_source.values()),2)
        b=discover([p,q],publishers(),AT,loader=lambda *_:payload(item(),item(url='https://one.example.org/a?utm_source=fixture#x')))
        self.assertEqual(sum(len(v) for v in b.by_source.values()),1)

    def test_official_id_not_reissued_with_changed_url_after_archive(self):
        p=provider();b=discover([p],publishers(),AT,loader=lambda *_:payload(item()))
        archived=[{'url':item()['link'],'discovery_origin':b.by_source['one'][0]['discovery_origin']}]
        b=discover([p],publishers(),AT,archive=archived,
                   loader=lambda *_:payload(item(url='https://one.example.org/new-path')))
        self.assertEqual(b.by_source,{})
        self.assertEqual(b.metrics[p['id']]['duplicates'],1)

    def test_bad_date_modified_time_and_promotions_are_held(self):
        rows=[item(published=''),item(published='invalid'),item(published=AT.date().isoformat()),
              item(published=(AT+dt.timedelta(days=1)).isoformat()),
              item(title='하나투어, ‘겨울여행 페스타’ 오픈'),item(title='일반 기업 AI 어시스턴트 도입')]
        p=provider();b=discover([p],publishers(),AT,loader=lambda *_:payload(*rows))
        r=b.metrics[p['id']];self.assertEqual((r['date_holds'],r['irrelevant']), (4,2))
        self.assertEqual(b.by_source,{})

    def test_domestic_issuer_is_not_korea_direct_evidence(self):
        p=provider()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            execute(publishers(),root/'data',root/'state',at=AT,loader=lambda _:feed(),providers=[p],
                    provider_loader=lambda *_:payload(item(title='런던, 의료친화 숙박시설 19개소 선정')))
            a=json.loads((root/'state/archive.json').read_text())['articles']
            record=next(x for x in a if x['url']==item()['link'])
            self.assertEqual(record['editorial']['tier'],'reference')

    def test_call_budget_interval_and_incremental_overlap(self):
        p=provider();p['since_parameter']='since'
        b=discover([p],publishers(),AT,loader=lambda *_:payload(item()))
        calls=[]
        later=AT+dt.timedelta(hours=1)
        again=discover([p],publishers(),later,previous=b.cursors,loader=lambda *a:calls.append(a))
        self.assertEqual(again.metrics[p['id']]['status'],'not_due');self.assertEqual(calls,[])
        b=discover([p],publishers(),AT+dt.timedelta(hours=2),previous=b.cursors,
                   loader=lambda p,q:(calls.append(q) or payload(item())))
        self.assertEqual(calls[0]['since'],c.iso(AT-dt.timedelta(days=1)))
        self.assertEqual(b.cursors[p['id']]['attempts'],2)
        q=provider('q');b=discover([p,q],publishers(),AT,max_calls=1,loader=lambda *_:payload())
        self.assertEqual(b.metrics['q']['status'],'deferred')

    def test_failure_redaction_continue_and_cursor_not_advanced(self):
        p,q=provider('p'),provider('q')
        def load(p,_):
            if p['id']=='p':raise HTTPError('https://api.example.org/?serviceKey=DO_NOT_LOG_TEST_SENTINEL',403,'private response',{},None)
            return payload(item())
        b=discover([p,q],publishers(),AT,loader=load)
        self.assertEqual(b.metrics['p']['status'],'error')
        self.assertNotIn('last_successful_at',b.cursors['p'])
        self.assertEqual(b.metrics['q']['status'],'ok')
        self.assertNotIn('DO_NOT_LOG_TEST_SENTINEL',json.dumps(b.metrics))
        self.assertNotIn('private response',json.dumps(b.metrics))

    def test_failed_multiquery_does_not_claim_ids_or_advance_success(self):
        p,q=provider('p'),provider('q');p['queries']=[{'page':'1'},{'page':'2'}];p['max_calls_per_run']=2
        def load(prov,params):
            if prov['id']=='p' and params.get('page')=='2':raise ValueError('private raw payload')
            return payload(item())
        b=discover([p,q],publishers(),AT,loader=load)
        self.assertEqual(b.metrics['p']['authorized_handoffs'],0)
        self.assertEqual(b.metrics['q']['authorized_handoffs'],1)
        self.assertNotIn('last_successful_at',b.cursors['p'])

    def test_json_and_xml_contracts_and_naver_original_link(self):
        p=provider();self.assertEqual(list(parse(p,payload(item())))[0],item())
        p['adapter']='xml_rows';p['response'].update(rows_path='./items/item',root_tag='root',container_path='./items')
        xml=b'<root><items><item><title>fixture</title><link>https://one.example.org/a</link></item></items></root>'
        self.assertEqual(list(parse(p,xml))[0]['title'],'fixture')
        p=provider();p['adapter']='naver_news'
        rows=list(parse(p,json.dumps({'items':[{'title':'fixture','link':'https://relay.example.org',
                        'originallink':'https://one.example.org/a','pubDate':AT.isoformat()}]}).encode()))
        self.assertEqual(rows[0]['link'],'https://one.example.org/a')
        b=discover([p],publishers(),AT,loader=lambda *_:json.dumps({'items':[{'title':item()['title'],
            'originallink':item()['link'],'pubDate':AT.isoformat()}]}).encode())
        self.assertEqual(b.by_source,{}) # No verified issuing institution supplied.

    def test_xml_and_json_error_envelopes_are_not_successful_empty_feeds(self):
        p=provider();p['adapter']='xml_rows'
        p['response'].update(rows_path='./items/item',root_tag='root',container_path='./items')
        for body in [b'<serviceError>denied</serviceError>',b'<root><error>denied</error></root>']:
            b=discover([p],publishers(),AT,loader=lambda *_:body)
            self.assertEqual(b.metrics[p['id']]['status'],'error')
            self.assertNotIn('last_successful_at',b.cursors[p['id']])
        b=discover([p],publishers(),AT,loader=lambda *_:b'<root><items/></root>')
        self.assertEqual(b.metrics[p['id']]['status'],'ok')
        p=provider();b=discover([p],publishers(),AT,loader=lambda *_:b'{"items":[],"errorCode":"AUTH"}')
        self.assertEqual(b.metrics[p['id']]['status'],'error')

    def test_engine_uses_existing_six_field_pipeline_and_revocation_restoration(self):
        p=provider();sources=publishers()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            load=lambda _:b'<rss><channel/></rss>'
            r=execute(sources,root/'data',root/'state',at=AT,loader=load,providers=[p],
                      provider_loader=lambda *_:payload(item(),item('two')))
            self.assertEqual(r['newsroom_count'],2)
            archive=json.loads((root/'state/archive.json').read_text())['articles']
            public=json.loads((root/'data/newsroom.json').read_text())['articles']
            self.assertTrue(all(set(x)=={'title','source','published_at','url','category','keywords'} for x in public))
            again=execute(sources,root/'data',root/'state',at=AT+dt.timedelta(hours=2),loader=load,providers=[p],
                          provider_loader=lambda *_:payload(item(),item('two')))
            self.assertEqual(again['new_newsroom_items'],0)
            p['capabilities']['publish']['status']='review'
            # Re-observation through an ordinary RSS must not strip provider rights history.
            rss=lambda u:feed('한국 관광산업 지원 정책 발표',link='https://'+u.rsplit('/',1)[-1]+'.example.org/a')
            held=execute(sources,root/'data',root/'state',at=AT+dt.timedelta(hours=4),loader=rss,providers=[p],
                         provider_loader=lambda *_:payload(item(),item('two')))
            self.assertEqual(held['newsroom_count'],0)
            self.assertEqual(len(json.loads((root/'state/archive.json').read_text())['articles']),2)
            p['capabilities']['publish']['status']='approved'
            restored=execute(sources,root/'data',root/'state',at=AT+dt.timedelta(hours=6),loader=load,providers=[p],
                             provider_loader=lambda *_:payload(item(),item('two')))
            self.assertEqual(restored['newsroom_count'],2)
            now=json.loads((root/'state/archive.json').read_text())['articles']
            for a in archive:
                b=next(x for x in now if x['id']==a['id'])
                for k in ['id','url','published_at','first_discovered_at','first_published_by_engine_at']:
                    self.assertEqual(a.get(k),b.get(k))

    def test_existing_source_review_and_unverified_record_still_fail_closed(self):
        p=provider();sources=publishers();sources[0]['publication']['status']='review'
        b=discover([p],sources,AT,loader=lambda *_:payload(item()))
        self.assertEqual(b.by_source,{})
        self.assertFalse(record_allowed({'discovery_origin':{}},[p],{}))
        self.assertTrue(record_allowed({'id':'legacy'},[p],{}))

    def test_pipeline_reprojects_provider_withdrawal_without_operational_side_effects(self):
        self.assertIn("'discovery_providers.json'", (c.ROOT/'.github/workflows/deploy.yml').read_text())
        from src.pipeline.policy import project, verify_public
        from src.pipeline.layout import copy_data,configuration
        import shutil
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);code=root/'code';stage=root/'stage';code.mkdir()
            for name in ['sources.json','operating_policy.json','reports_sources.json','macro_sources.json']:
                shutil.copyfile(c.ROOT/name,code/name)
            copy_data(c.ROOT,stage,configuration())
            # Insert one clearly synthetic, fully licensed row only into the temp snapshot.
            sources=json.loads((code/'sources.json').read_text())['sources'];target=next(x for x in sources if x['id']=='traveltimes')
            p=provider();p['publishers']['one']={'source_id':target['id'],'publisher_id':target['coverage']['publisher_id'],
                'verified':True,'evidence_url':'https://example.org/fixture','article_domains':target['article_domains']}
            itemdata=item(url='https://www.traveltimes.co.kr/news/discovery-fixture-only')
            execute(sources,stage/'site/data',stage/'collector_state',at=AT,providers=[p],
                    loader=lambda _:b'<rss><channel/></rss>',provider_loader=lambda *_:payload(itemdata))
            p['capabilities']['publish']['status']='review'
            (code/'discovery_providers.json').write_text(json.dumps({'providers':[p]}))
            project(stage,code,AT);verify_public(stage,code)
            self.assertNotIn(itemdata['link'],[a['url'] for a in json.loads((stage/'site/data/newsroom.json').read_text())['articles']])


class TransportTests(unittest.TestCase):
    def rules(self, lines=()):
        r=RobotFileParser();r.parse(list(lines));return 'https://api.example.org',r

    def test_endpoint_and_robots_checked_before_credentials_or_request(self):
        p=provider();transport=Transport()
        with patch.object(transport,'_open') as request,patch.object(transport,'_rules',return_value=self.rules(['User-agent: *','Disallow: /'])):
            with self.assertRaisesRegex(ValueError,'robots_not_allowed'):
                transport(p,{})
            request.assert_not_called()
        for url in ['http://api.example.org/list','https://localhost/a','https://api.example.org/list?serviceKey=forbidden',
                    'https://user@api.example.org/list','https://other.example.org/list']:
            p['endpoint']=url
            self.assertFalse(endpoint_allowed(p))

    def test_missing_credentials_and_auth_query_plan_fail_before_open(self):
        p=provider();p['auth']=[{'env':'TOURISM_TEST_MISSING_CREDENTIAL','placement':'query','name':'serviceKey'}]
        transport=Transport()
        with patch.object(transport,'_rules',return_value=self.rules()),patch.object(transport,'_open') as request:
            with patch.dict('os.environ',{},clear=True):
                with self.assertRaisesRegex(ValueError,'credentials_missing'):transport(p,{})
            with self.assertRaisesRegex(ValueError,'credentials_not_allowed'):transport(p,{'serviceKey':'not-a-credential-fixture'})
            request.assert_not_called()

    def test_header_and_query_auth_no_redirects_or_raw_error_in_metrics(self):
        from unittest.mock import MagicMock
        p=provider();p['auth']=[{'env':'TOURISM_TEST_ONLY','placement':'header','name':'X-Fixture-Auth'}]
        transport=Transport();response=MagicMock();response.__enter__.return_value.read.return_value=payload(item())
        with patch.object(transport,'_rules',return_value=self.rules()),patch.object(transport,'_open',return_value=response) as request,patch.dict('os.environ',{'TOURISM_TEST_ONLY':'DO_NOT_LOG_TEST_SENTINEL'}):
            transport(p,{'q':'관광산업'})
            req=request.call_args.args[0]
            self.assertEqual(req.get_header('X-fixture-auth'),'DO_NOT_LOG_TEST_SENTINEL')
            self.assertNotIn('DO_NOT_LOG_TEST_SENTINEL',req.full_url)
        p['auth'][0].update(placement='query',name='serviceKey')
        with patch.object(transport,'_rules',return_value=self.rules()),patch.object(transport,'_open',side_effect=HTTPError('https://api.example.org/?serviceKey=DO_NOT_LOG_TEST_SENTINEL',302,'redirect',{'Location':'https://elsewhere.example.org'},None)) as request,patch.dict('os.environ',{'TOURISM_TEST_ONLY':'DO_NOT_LOG_TEST_SENTINEL'}):
            b=discover([p],publishers(),AT,loader=transport)
            self.assertEqual(request.call_count,1)
            self.assertEqual(b.metrics[p['id']]['status'],'error')
            self.assertNotIn('DO_NOT_LOG_TEST_SENTINEL',json.dumps(b.metrics))

    def test_rate_limit_and_response_size_boundaries(self):
        from unittest.mock import MagicMock
        p=provider();transport=Transport()
        with patch.object(transport,'_rules',return_value=self.rules(['User-agent: *','Crawl-delay: 10'])),patch.object(transport,'_open') as request:
            with self.assertRaisesRegex(ValueError,'crawl_delay'):transport(p,{})
            request.assert_not_called()
        response=MagicMock();response.__enter__.return_value.read.return_value=b'x'*(2*1024*1024+1)
        with patch.object(transport,'_rules',return_value=self.rules()),patch.object(transport,'_open',return_value=response):
            with self.assertRaisesRegex(ValueError,'response_too_large'):transport(p,{})

    def test_verified_single_issuer_rss_and_primary_failure_fallback(self):
        p=provider();p['adapter']='rss';p['fixed_publisher_code']='one'
        def offline(_):raise OSError('isolated original feed failure')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            r=execute(publishers()[:1],root/'data',root/'state',at=AT,providers=[p],loader=offline,
                      provider_loader=lambda *_:feed('한국 관광산업 지원 정책 발표',link='https://one.example.org/a'))
            self.assertEqual(r['newsroom_count'],1)
            self.assertEqual(r['discovery_status'],'partial')
            self.assertEqual(r['sources'][0]['primary_feed_status'],'failed_using_verified_provider_fallback')
            self.assertEqual(r['discovery_providers'][p['id']]['new_public_news'],1)


class RateLimitTests(unittest.TestCase):
    def test_retry_after_survives_without_response_or_secret_storage(self):
        p=provider()
        def busy(*_):raise HTTPError('https://api.example.org/',429,'private',{'Retry-After':'10800'},None)
        b=discover([p],publishers(),AT,loader=busy)
        self.assertEqual(b.metrics[p['id']]['error_kind'],'rate_limited')
        with patch('src.news_discovery.Transport.__call__') as load:
            again=discover([p],publishers(),AT+dt.timedelta(hours=2),previous=b.cursors)
            load.assert_not_called()
            self.assertEqual(again.metrics[p['id']]['status'],'deferred')
        self.assertNotIn('last_successful_at',b.cursors[p['id']])


if __name__=='__main__':unittest.main()

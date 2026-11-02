"""Official catalog adapters. Extract headings, bibliographic dates and links only.
No PDF/image downloads, report text, descriptions or embedded attachments returned.
"""
import json
import re
import urllib.parse
from .html import DOM


def json_schemas(payload):
    text=payload.decode('utf-8','replace') if isinstance(payload,bytes) else payload
    found=[]
    for attrs,raw in re.findall(r'<script\b([^>]*)>(.*?)</script>',text,re.S|re.I):
        if not re.search(r'application/ld\+json',attrs,re.I):continue
        try:data=json.loads(raw)
        except (ValueError,TypeError):continue
        def walk(obj):
            if isinstance(obj,dict):
                found.append({k:obj[k] for k in ('@type','datePublished','dateCreated','headline','name','url') if k in obj})
                if '@graph' in obj:walk(obj['@graph'])
            elif isinstance(obj,list):
                for v in obj:walk(v)
        walk(data)
    return found


def pairs(dom):
    result={}
    for dl in (dom.root if hasattr(dom,'root') else dom).all('dl'):
        key=None
        for n in dl.children:
            if n.tag=='dt':key=n.text()
            elif n.tag=='dd' and key:result[key]=n.text();key=None
    return result


def discover(source, fetch):
    adapter=source['adapter'];seen_pages=set();queue=[{'url':u} for u in source.get('catalog_urls',[])]+list(source.get('catalog_requests',[]));count=0
    while queue and count<source.get('max_catalog_pages',8):
        request=queue.pop(0);url=request['url'];form=request.get('form')
        key=json.dumps(request,sort_keys=True)
        if key in seen_pages:continue
        seen_pages.add(key);count+=1
        payload=fetch(url, form=form);dom=DOM(payload)
        if adapter=='yanolja':
            raw=payload.decode('utf-8','replace')
            match=re.search(r'let lists\s*=\s*(\[.*?\]);',raw,re.S)
            # The cards themselves carry an official title/date pair. JSON is
            # used only when a matching catalog-provided detail link exists.
            linked={urllib.parse.urlsplit(u).path:u for u,t in dom.links(url) if '/view/' in u}
            if not match and not any('/view/' in u for u,t in dom.links(url)):
                raise ValueError('catalog_schema_missing_or_access_challenge')
            if match:
                entries=json.loads(match[1])
                for row in entries:
                    provider_id=str(row.get('RESEARCH_IDX',''))
                    target=next((v for k,v in linked.items() if k.endswith('/'+provider_id)),None)
                    if target:
                        yield {'title':row['TITLE'],'url':target,'provider_id':provider_id,
                               'catalog_url':url,'catalog_date':row.get('INS_DATE'),'date_kind':'registered',
                               'series':urllib.parse.urlsplit(target).path.split('/')[1]}
            else:
                for a in dom.root.all('a'):
                    target=urllib.parse.urljoin(url,a.attrs.get('href',''))
                    if '/view/' not in urllib.parse.urlsplit(target).path:continue
                    dates=[n.text() for n in a.all('dt') if re.fullmatch(r'\d{4}\.\d{2}\.\d{2}',n.text())]
                    titles=[n.text() for n in a.all() if n.tag in ('h2','h3','h4')]
                    if not titles:
                        titles=[n.text() for n in a.all() if any(n.has(c) for c in ('title','tit'))]
                    if titles:
                        yield {'title':titles[0],'url':target,'provider_id':urllib.parse.urlsplit(target).path.split('/')[-1],
                               'catalog_url':url,'catalog_date':dates[0] if dates else None,'date_kind':'registered',
                               'series':urllib.parse.urlsplit(target).path.split('/')[1]}
            for target,label in dom.links(url):
                if re.search(r'/list\?',target) and urllib.parse.urlsplit(target).path==urllib.parse.urlsplit(url).path:
                    if dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(target).query)).get('page')!='1':queue.append({'url':target})
        elif adapter=='etc':
            if not any('/reports/' in a.attrs.get('href','') for h in dom.root.all('h3') for a in h.all('a')) and not any(n.has('js-wpv-loop') for n in dom.root.all()):
                raise ValueError('catalog_schema_missing_or_access_challenge')
            for heading in dom.root.all('h3'):
                for a in heading.all('a'):
                    target=urllib.parse.urljoin(url,a.attrs.get('href',''))
                    if '/reports/' in urllib.parse.urlsplit(target).path and a.text():
                        yield {'title':a.text(),'url':target,'provider_id':urllib.parse.urlsplit(target).path.rstrip('/').split('/')[-1], 'catalog_url':url}
            for target,label in dom.links(url):
                if 'wpv_paged=' in target and urllib.parse.urlsplit(target).path=='/publications/':queue.append({'url':target})
        elif adapter=='phocuswright':
            if not any('/Travel-Research/' in u and len(urllib.parse.urlsplit(u).path.strip('/').split('/'))>=3 for u,t in dom.links(url)):
                raise ValueError('catalog_schema_missing_or_access_challenge')
            found=set()
            for target,label in dom.links(url):
                path=urllib.parse.urlsplit(target).path
                if path.startswith('/Travel-Research/') and len(path.strip('/').split('/'))>=3 and target not in found:
                    found.add(target)
                    yield {'url':target,'provider_id':path.rstrip('/'),'catalog_url':url}
        elif adapter=='oecd':
            links=[(u,t) for u,t in dom.links(url) if urllib.parse.urlsplit(u).hostname=='www.oecd.org' and re.fullmatch(r'/en/publications/oecd-tourism-trends-and-policies-20\d{2}_[a-z0-9-]+\.html',urllib.parse.urlsplit(u).path)]
            if not links:raise ValueError('catalog_schema_missing_or_access_challenge')
            for target,title in dict(links).items():
                yield {'url':target,'title':title,'provider_id':urllib.parse.urlsplit(target).path.rsplit('_',1)[-1].removesuffix('.html'),'catalog_url':url}
        elif adapter=='koti':
            anchors=[a for a in dom.root.all('a') if a.has('txt') and re.search(r'/(bassRsrchReprt|anytmRsrchReprt)View\.do',urllib.parse.urljoin(url,a.attrs.get('href','')))]
            if not any(n.has('comm_pagination') for n in dom.root.all()) and not anchors:raise ValueError('catalog_schema_missing_or_access_challenge')
            for a in anchors:
                titles=[n.text() for n in a.all('p') if n.has('title')]
                if len(titles)!=1:raise ValueError('catalog_report_title_structure_changed')
                title=titles[0]
                if not re.search(r'항공|공항|관광|여객',title) or ('화물' in title and not re.search(r'여객|관광',title)):continue
                target=urllib.parse.urljoin(url,a.attrs['href']);parts=urllib.parse.urlsplit(target);qid=urllib.parse.parse_qs(parts.query).get('bbs_no',[])
                if len(qid)!=1 or not qid[0].isdigit():raise ValueError('catalog_report_id_missing')
                yield {'title':title,'url':urllib.parse.urlunsplit((parts.scheme,parts.netloc,parts.path,'bbs_no='+qid[0],'')),'provider_id':qid[0],'catalog_url':url}
        elif adapter=='kcti':
            if not any(n.has('totalcnt') for n in dom.root.all('p')) and not any(n.has('thumbnaillist_txt') for n in dom.root.all('a')):
                raise ValueError('catalog_schema_missing_or_access_challenge')
            for li in dom.root.all('li'):
                if not any(n.has('thumbnaillist_txt') for n in li.all('a')):continue
                headings=[n.text() for n in li.all('h4')]
                anchor=next((n for n in li.all('a') if n.has('thumbnaillist_txt')),None)
                match=re.search(r"contentsView\('([a-f0-9]+)'\)",anchor.attrs.get('href','')) if anchor else None
                fields=pairs(li)
                if match and headings:
                    target=source['detail_url']+'?'+urllib.parse.urlencode({'board_id':'2','contents_id':match[1]})
                    yield {'title':headings[0],'url':target,'provider_id':match[1],'catalog_url':url,
                           'catalog_date':fields.get('발간년도'),'date_kind':'publication_year'}
            raw=payload.decode('utf-8','replace')
            for page in re.findall(r'go_Page\([\"\']?(\d+)',raw):
                if form and page!=str(form.get('miv_pageNo','1')):
                    queue.append({'url':url,'form':{**form,'miv_pageNo':page}})
        else:raise ValueError('unsupported_report_adapter')


def verify(source, candidate, payload):
    dom=DOM(payload);meta=dom.meta();schemas=json_schemas(payload);adapter=source['adapter']
    result=dict(candidate);result['access_type']='미확인'
    if adapter=='oecd':
        title=meta.get('citation_title');date=meta.get('citation_publication_date');doi=meta.get('citation_doi','')
        if meta.get('template')!='report-summary-page' or not title or title!=meta.get('og:title') or not date or not re.fullmatch(r'https://doi.org/10\.1787/[a-z0-9-]+',doi):raise ValueError('oecd_bibliographic_metadata_missing')
        if meta.get('citation_author')!='OECD' or meta.get('citation_publisher')!='OECD Publishing':raise ValueError('oecd_publisher_unverified')
        if not any(n.attrs.get('itemprop')=='datePublished' and n.attrs.get('datetime')==date.replace('/','-') for n in dom.root.all('time')):raise ValueError('oecd_publication_date_mismatch')
        result.update(title=title,published_at=date.replace('/','-'),date_kind='official_publication',doi=doi,authors='OECD')
        # Publicly offered PDF link is access evidence only; never follow it.
        if meta.get('citation_pdf_url') and any(u==meta['citation_pdf_url'] for u,t in dom.links(candidate['url'])):result['access_type']='무료 공개'
    elif adapter=='koti':
        panels=[n for n in dom.root.all('div') if n.has('view_detail_top')]
        if len(panels)!=1:raise ValueError('koti_bibliographic_panel_missing')
        panel=panels[0];headings=[n for n in panel.all('div') if n.has('view_detail_top-title')]
        titles=[n.text() for h in headings for n in h.all('strong') if n.has('title')]
        if titles!=[candidate['title']]:raise ValueError('report_title_mismatch')
        fields={}
        for li in panel.all('li'):
            labels=[n.text() for n in li.all('em')];values=[n.text() for n in li.all('p')]
            if len(labels)==len(values)==1:fields[labels[0]]=values[0]
        if not fields.get('발간일') or not fields.get('저자'):raise ValueError('koti_publication_date_or_authors_missing')
        license_panels=[n for n in dom.root.all('div') if n.has('kogl')]
        marks=[re.search(r'/img_nuri_([1-4])\.',n.attrs.get('src','')) for panel in license_panels for n in panel.all('img')]
        types={int(m[1]) for m in marks if m}
        if len(types)!=1:raise ValueError('missing_per_record_KOGL_scope')
        result.update(published_at=fields['발간일'],date_kind='official_publication',authors=fields['저자'],kogl_type=types.pop())
        if any('commonFileDownload(' in n.attrs.get('onclick','') for n in panel.all('button')):result['access_type']='무료 공개'
    elif adapter=='etc':
        result['title']=meta.get('og:title',candidate['title'])
        result['published_at']=meta.get('article:published_time')
        result['date_kind']='official_page_first_publication'
        # Official landing offers a public download; never request the file.
        if any(re.search(r'\.pdf(?:$|\?)',u,re.I) for u,t in dom.links(candidate['url'])):result['access_type']='무료 공개'
        if not result['published_at']:
            result['published_at']=next((o['datePublished'] for o in schemas if o.get('datePublished')),None)
        if not meta.get('og:title') or '/reports/' not in candidate['url']:raise ValueError('invalid_report_landing')
    elif adapter=='yanolja':
        headers=[n.text() for n in dom.root.all('h3') if n.has('title')]
        if not headers or not candidate.get('title') or candidate['title'] not in headers:raise ValueError('report_title_mismatch')
        fields=pairs(dom.root)
        result['published_at']=fields.get('발행일') or fields.get('발간일') or fields.get('등록일')
        result['date_kind']='official_publication' if fields.get('발행일') or fields.get('발간일') else 'registered'
        if any('다운로드' in t or 'Download' in t for u,t in dom.links(candidate['url'])):result['access_type']='무료 공개'
    elif adapter=='kcti':
        fields=pairs(dom.root)
        headers=[n.text() for n in dom.root.all('h3')]
        if not any(candidate['title'] in h for h in headers):raise ValueError('report_title_mismatch')
        result['published_at']=fields.get('발행일') or fields.get('발간일') or fields.get('발간년도')
        result['date_kind']='official_publication' if fields.get('발행일') or fields.get('발간일') else 'publication_year'
        result['authors']=fields.get('저자','')
        text=payload.decode('utf-8','replace')
        license_match=re.search(r'new_img_opencode([1-4])\.',text)
        result['kogl_type']=int(license_match[1]) if license_match else None
        if fields.get('공개여부')=='공개':result['access_type']='무료 공개'
    elif adapter=='phocuswright':
        titles=[n.text() for n in dom.root.all('h1')]
        if not titles:raise ValueError('missing_report_title')
        result['title']=titles[0]
        result['published_at']=next((o['datePublished'] for o in schemas if o.get('datePublished')),None)
        result['date_kind']='official_page_first_publication'
        # Restrict inspection to labeled publication/catalog metadata and
        # purchase controls. Never copy the report Summary or Description.
        if any(n.has('jq-add-basket') and n.text().strip().lower()=='add to cart' for n in dom.root.all('a')):result['access_type']='유료'
        if not result['published_at']:
            # Published: month/year is official but is not a fabricated day.
            for n in dom.root.all():
                if n.tag not in ('span','p','li'):continue
                m=re.fullmatch(r'Published:\s*([A-Za-z]+)\s+(20\d\d)',n.text())
                if m:
                    import datetime as dt
                    result['published_at']=dt.datetime.strptime(m[1]+' '+m[2],'%B %Y').strftime('%Y-%m');break
    return result

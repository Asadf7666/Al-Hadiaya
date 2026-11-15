"""Direct receipt printing: plain ESC/POS sent straight to a Windows printer, with no print dialog.

Works with thermal receipt printers that accept ESC/POS (Epson TM, TVS, Posiflex,
Rugtek and most 58 mm and 80 mm models) installed as a Windows printer. The
bill is laid out as fixed-width text, so it prints at the printer's full speed.
"""
import datetime as dt,json,os

ESC=b'\x1b';GS=b'\x1d'
INIT=ESC+b'@';CENTRE=ESC+b'a\x01';LEFT=ESC+b'a\x00';BOLD=ESC+b'E\x01';PLAIN=ESC+b'E\x00'
LARGE=GS+b'!\x11';NORMAL=GS+b'!\x00';CUT=GS+b'V\x42\x00';DRAWER=ESC+b'p\x00\x19\xfa'
COLUMNS=('32','42','48')

def printers():
    """Names of the printers installed for this Windows account."""
    if os.name!='nt':return []
    import ctypes
    from ctypes import wintypes
    class Info(ctypes.Structure):_fields_=[('pPrinterName',wintypes.LPWSTR),('pServerName',wintypes.LPWSTR),('Attributes',wintypes.DWORD)]
    spool=ctypes.WinDLL('winspool.drv',use_last_error=True);needed=wintypes.DWORD();count=wintypes.DWORD();flags=2|4
    spool.EnumPrintersW(flags,None,4,None,0,ctypes.byref(needed),ctypes.byref(count))
    if not needed.value:return []
    buffer=ctypes.create_string_buffer(needed.value)
    if not spool.EnumPrintersW(flags,None,4,buffer,needed.value,ctypes.byref(needed),ctypes.byref(count)):return []
    return sorted(ctypes.cast(buffer,ctypes.POINTER(Info))[i].pPrinterName for i in range(count.value))

def send(name,data):
    """Hand raw bytes to the Windows spooler for one printer."""
    if os.name!='nt':raise ValueError('Direct printing works in the Windows app. Use Print / Save PDF here.')
    import ctypes
    from ctypes import wintypes
    class Doc(ctypes.Structure):_fields_=[('pDocName',wintypes.LPWSTR),('pOutputFile',wintypes.LPWSTR),('pDatatype',wintypes.LPWSTR)]
    spool=ctypes.WinDLL('winspool.drv',use_last_error=True);handle=wintypes.HANDLE()
    spool.OpenPrinterW.argtypes=[wintypes.LPWSTR,ctypes.POINTER(wintypes.HANDLE),ctypes.c_void_p]
    spool.StartDocPrinterW.argtypes=[wintypes.HANDLE,wintypes.DWORD,ctypes.POINTER(Doc)]
    spool.WritePrinter.argtypes=[wintypes.HANDLE,ctypes.c_char_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
    for fn in (spool.StartPagePrinter,spool.EndPagePrinter,spool.EndDocPrinter,spool.ClosePrinter):fn.argtypes=[wintypes.HANDLE]
    if not spool.OpenPrinterW(name,ctypes.byref(handle),None):
        raise ValueError(f'Printer "{name}" was not found. Choose the receipt printer again in Settings.')
    try:
        if not spool.StartDocPrinterW(handle,1,ctypes.byref(Doc('Al Hadiya receipt',None,'RAW'))):raise ValueError('The printer did not accept the job. Check that it is switched on and online.')
        try:
            written=wintypes.DWORD()
            if not spool.StartPagePrinter(handle) or not spool.WritePrinter(handle,data,len(data),ctypes.byref(written)) or written.value!=len(data):
                raise ValueError('The receipt could not be sent to the printer. Check paper, cable and power.')
            spool.EndPagePrinter(handle)
        finally:spool.EndDocPrinter(handle)
    finally:spool.ClosePrinter(handle)

def _text(value):
    # Receipt printers hold a small character set; anything else becomes a plain substitute.
    return str(value).replace('₹','Rs.').replace('·','-').replace('–','-').replace('—','-').replace('’',"'").replace('−','-').encode('cp437','replace')
def _rupees(paise):return f'{paise/100:,.2f}'
def _quantity(value):return f'{value:g}'
def _pair(left,right,width):
    left,right=str(left),str(right);room=width-len(right)-1
    return _text((left[:room] if len(left)>room else left).ljust(room)+' '+right)+b'\n'
def _wrap(text,width):
    words,lines,line=str(text).split(),[],''
    for word in words:
        while len(word)>width:lines.append(word[:width]);word=word[width:]
        if len(line)+len(word)+(1 if line else 0)>width:lines.append(line);line=word
        else:line=(line+' '+word).strip()
    return lines+([line] if line else [])
def _centre(text,width):return b''.join(_text(line)+b'\n' for line in _wrap(text,width))
def _when(stamp):
    try:return dt.datetime.fromisoformat(stamp).strftime('%d-%m-%Y %I:%M %p')
    except ValueError:return stamp
def _qr(text):
    """ESC/POS QR code (model 2, error correction M)."""
    data=text.encode('utf-8');size=len(data)+3
    return (GS+b'(k\x04\x001A2\x00'+GS+b'(k\x03\x001C\x05'+GS+b'(k\x03\x001E1'+GS+b'(k'+bytes([size%256,size//256])+b'1P0'+data+GS+b'(k\x03\x001Q0')

TITLES={'sale_return':'CREDIT NOTE','purchase_return':'DEBIT NOTE','purchase':'PURCHASE RECORD'}
def receipt(doc,columns=48,drawer=False):
    """ESC/POS bytes for one saved document. `doc` is a documents row with its snapshot parsed."""
    width=int(columns);snap=doc['snapshot'];shop=snap['shop'];note=doc['kind'] in ('sale_return','purchase_return');rule=_text('-'*width)+b'\n'
    out=[INIT,CENTRE,BOLD,LARGE if len(shop['name'])*2<=width else NORMAL,_centre(shop['name'],width//2 if len(shop['name'])*2<=width else width),NORMAL,PLAIN]
    if shop.get('address'):out.append(_centre(shop['address'],width))
    if shop.get('phone'):out.append(_centre('Tel: '+shop['phone'],width))
    out.append(_centre('GSTIN: '+shop['gstin'] if shop.get('gst_enabled') else 'Composition taxable person, not eligible to collect tax on supplies' if shop.get('composition') else 'GST not collected',width))
    if shop.get('fssai'):out.append(_centre('FSSAI Lic. No. '+shop['fssai'],width))
    title=TITLES.get(doc['kind']) or ('TAX INVOICE' if shop.get('gst_enabled') else 'BILL OF SUPPLY' if shop.get('composition') else 'SALE RECEIPT')
    out+=[BOLD,_centre(('REVERSED - ' if doc['reversed'] else '')+title,width),PLAIN,LEFT,rule,_text('No: '+doc['id'])+b'\n',_text(_when(doc['date'])+' - '+doc['location'])+b'\n']
    if snap.get('original_id'):out+=[_text('Against: '+snap['original_id'])+b'\n']+[_text(line)+b'\n' for line in _wrap('Reason: '+snap.get('reason',''),width)]
    party=snap.get('party') or {}
    out+=[_text(line)+b'\n' for line in _wrap(('Supplier: ' if doc['kind'].startswith('purchase') else 'Customer: ')+(party.get('name') or 'Walk-in customer'),width)]
    if party.get('gstin'):out.append(_text('GSTIN: '+party['gstin'])+b'\n')
    out.append(rule)
    for item in snap['items']:
        out+=[_text(line)+b'\n' for line in _wrap(item['name'],width)]
        tax=f" GST {item['gst']:g}%" if shop.get('gst_enabled') else ''
        out.append(_pair(f"  {_quantity(item['quantity'])} {item['unit']} x {_rupees(item['price'])}{tax}",_rupees(item['total']),width))
    out.append(rule)
    if not note and doc['discount']:out.append(_pair('Discount included',_rupees(doc['discount']),width))
    if shop.get('gst_enabled'):
        out.append(_pair('Taxable value',_rupees(doc['total']-doc['tax']-snap.get('round_off',0)),width))
        if snap.get('tax_type')=='IGST':out.append(_pair('IGST',_rupees(sum(i.get('igst_amount',0) for i in snap['items'])),width))
        else:
            out.append(_pair('CGST',_rupees(sum(i.get('cgst_amount',0) for i in snap['items'])),width));out.append(_pair('SGST',_rupees(sum(i.get('sgst_amount',0) for i in snap['items'])),width))
        cess=sum(i.get('cess_amount',0) for i in snap['items'])
        if cess:out.append(_pair('Cess',_rupees(cess),width))
    if snap.get('round_off'):out.append(_pair('Round off',('+' if snap['round_off']>0 else '-')+_rupees(abs(snap['round_off'])),width))
    out+=[BOLD,LARGE,_pair('RETURNED' if note else 'TOTAL','Rs.'+_rupees(doc['total']),width//2),NORMAL,PLAIN]
    tenders=snap.get('payments') or ([{'method':doc['payment'],'amount':doc['paid']}] if doc['paid'] else [])
    for tender in tenders:out.append(_pair(('Refunded' if doc['kind']=='sale_return' else 'Received back' if note else 'Paid')+' - '+tender['method'],_rupees(tender['amount']),width))
    if note and snap.get('credit'):out.append(_pair('Adjusted against dues',_rupees(snap['credit']),width))
    due=0 if note else doc['total']-doc['paid']
    if due:out.append(_pair('Balance due',_rupees(due),width))
    upi=sum(t['amount'] for t in tenders if t['method']=='UPI');amount=due or upi
    if doc['kind']=='sale' and not doc['reversed'] and shop.get('upi_id') and amount:
        from urllib.parse import quote
        link=f"upi://pay?pa={quote(shop['upi_id'],safe='')}&pn={quote(shop['name'],safe='')}&am={amount/100:.2f}&cu=INR&tn={quote(doc['id'],safe='')}"
        out+=[CENTRE,b'\n',_qr(link),_centre(f'Scan to pay Rs.{_rupees(amount)}',width),_centre(shop['upi_id'],width),LEFT]
    if doc.get('reference') and not note:out+=[_text(line)+b'\n' for line in _wrap('Ref: '+doc['reference'],width)]
    out+=[CENTRE,b'\n',_centre('Thank you for shopping with us.',width),b'\n\n\n\n',CUT]
    if drawer and any(t['method']=='Cash' for t in tenders):out.append(DRAWER)
    return b''.join(out)

def day_end(shift,shop_name,columns=48):
    width=int(columns);m=shift['summary'];rule=_text('-'*width)+b'\n'
    out=[INIT,CENTRE,BOLD,_centre(shop_name,width),_centre('DAY-END REPORT',width),PLAIN,LEFT,rule,
         _text('Opened: '+_when(shift['opened'])+' '+shift['opened_by'])+b'\n',_text('Closed: '+_when(shift['closed'])+' '+shift['closed_by'])+b'\n',rule,
         _pair(f"Sales ({m['sales']} bills)",_rupees(m['sales_total']),width),_pair(f"Returns ({m['returns']})",'-'+_rupees(m['returns_total']),width),
         _pair('Sold on credit',_rupees(m['credit_given']),width),_pair('Collected from customers',_rupees(m['collections']),width),
         _pair('Paid to suppliers',_rupees(m['supplier_payments']),width),_pair('Expenses',_rupees(m['expenses']),width),rule]
    for method in ('Cash','UPI','Card','Bank'):
        out.append(_pair(method+' in',_rupees(m['methods'][method]['in']),width))
        if m['methods'][method]['out']:out.append(_pair(method+' out',_rupees(m['methods'][method]['out']),width))
    difference=m.get('difference',0)
    out+=[rule,_pair('Opening float',_rupees(m['opening_float']),width),BOLD,_pair('Cash expected',_rupees(m['expected_cash']),width),PLAIN,
          _pair('Cash counted',_rupees(m.get('counted_cash',0)),width),_pair('Difference' if not difference else 'Over' if difference>0 else 'Short',_rupees(abs(difference)),width)]
    if shift.get('note'):out+=[_text(line)+b'\n' for line in _wrap('Note: '+shift['note'],width)]
    out+=[b'\n\n',_text('Cashier: ____________  Owner: ____________'[:width])+b'\n\n\n\n',CUT]
    return b''.join(out)

def act(shop,action,data):
    """print_receipt, print_shift, print_test and open_drawer for this PC's receipt printer."""
    with shop.connect() as db:
        settings=shop.settings(db);name=settings.get('receipt_printer') or ''
        if not name:raise ValueError('Choose a receipt printer in Settings first.')
        columns=settings.get('receipt_columns') if settings.get('receipt_columns') in COLUMNS else '48'
        if action=='print_receipt':
            row=db.execute('SELECT * FROM documents WHERE id=?',(str(data.get('id','')),)).fetchone()
            if not row:raise ValueError('Bill not found.')
            doc=dict(row);doc['snapshot']=json.loads(doc['snapshot'])
            payload=receipt(doc,columns,bool(settings.get('drawer_kick')) and not data.get('reprint'))
        elif action=='print_shift':
            row=db.execute("SELECT * FROM shifts WHERE id=? AND closed<>''",(int(data.get('id',0)),)).fetchone()
            if not row:raise ValueError('Day-end report not found.')
            payload=day_end({**dict(row),'summary':json.loads(row['summary'])},settings['name'],columns)
        elif action=='open_drawer':payload=DRAWER
        else:
            payload=INIT+CENTRE+BOLD+_centre(settings['name'],int(columns))+PLAIN+_centre('Receipt printer test',int(columns))+LEFT+_text('1234567890'*5)[:int(columns)]+b'\n'+_pair('Columns per line',columns,int(columns))+_pair('Rupee amount','Rs.1,234.50',int(columns))+b'\n\n\n\n'+CUT
    send(name,payload)
    return {'ok':True,'printer':name}

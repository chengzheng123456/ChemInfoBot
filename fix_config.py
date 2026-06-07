import sys 
content=open('config.py','r',encoding='utf-8').read() 
lines=content.split(chr(10)) 
result=[] 
seen_main=False 
seen_val=False 
last_good=len(lines) 
for i in range(len(lines)-1,-1,-1): 
    line=lines[i] 
    if 'validate_config' in line and not seen_val: 
        seen_val=True 
        last_good=i+7 
    if '__main__' in line and not seen_main: 
        seen_main=True 
        break 
content=chr(10).join(lines[:last_good]) 
content=content.strip()+chr(10) 
open('config.py','w',encoding='utf-8').write(content) 
print('config.py cleaned: '+str(last_good)+' lines kept') 

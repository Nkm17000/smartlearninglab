import React,{useEffect,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Badge,Button,Card,Empty,ErrorState,Header,Loading} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function StudentCertificatesScreen(){
 const [items,setItems]=useState(null),[error,setError]=useState('');
 const load=async()=>{try{setError('');setItems(api.listOf(await api.certificates()))}catch(e){setError(e.message)}};
 useEffect(()=>{load()},[]);
 if(error)return <AppShell><Header title="Certificates"/><ErrorState title="Certificates could not load" message={error} onRetry={load}/></AppShell>;
 if(!items)return <AppShell><Loading label="Loading certificates…"/></AppShell>;
 return <AppShell><Header eyebrow="Achievements" title="Certificates" subtitle="Your verified course completion certificates."/>
  {items.length===0?<Empty title="No certificates yet" message="Complete all lessons in a course to unlock its certificate."/>:items.map(c=><Card key={api.idOf(c)} style={{borderColor:'#F9A8D4'}}><Text style={{fontSize:22}}>🏆</Text><Text style={{fontSize:18,fontWeight:'900',color:colors.navy,marginTop:8}}>{c.course_name}</Text><Text style={{color:colors.muted,marginTop:4}}>Issued to {c.student_name}</Text><Text style={{fontSize:12,color:colors.muted,marginTop:5}}>Certificate ID: {c.certificate_id}</Text><Button title="Certificate ready" variant="success" onPress={()=>Alert.alert('Certificate',`ID: ${c.certificate_id}\nUse the certificate PDF endpoint to download it.`)} style={{marginTop:12}}/></Card>)}
 </AppShell>;
}

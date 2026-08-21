import React,{useEffect,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Badge,Button,Card,Empty,ErrorState,Field,Header,Loading,Select} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

const roles=[
 {value:'admin',label:'Admin'},
 {value:'content_admin',label:'Content Admin'},
 {value:'instructor',label:'Instructor'},
 {value:'support_admin',label:'Support Admin'},
];
export default function AdminUsersScreen(){
 const [items,setItems]=useState(null),[error,setError]=useState(''),[show,setShow]=useState(false);
 const [name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[role,setRole]=useState('admin');
 const load=()=>{setError('');api.admins().then(x=>setItems(api.listOf(x))).catch(e=>setError(e.message))};useEffect(load,[]);
 const create=async()=>{try{await api.createAdmin({name,email,password,role});setName('');setEmail('');setPassword('');setRole('admin');setShow(false);load()}catch(e){Alert.alert('Create admin',e.message)}};
 const status=async(u)=>{try{await api.adminStatus(api.idOf(u),!u.is_active);load()}catch(e){Alert.alert('Status',e.message)}};
 const remove=async(u)=>{try{await api.deleteAdmin(api.idOf(u));load()}catch(e){Alert.alert('Delete',e.message)}};
 if(error)return <AppShell><ErrorState title="Admin users could not load" message={error} onRetry={load}/></AppShell>;
 return <AppShell><Header eyebrow="Root Admin" title="Admin & Staff" subtitle="Create and manage different admin roles." right={<Button title={show?'Close':'+ Create Admin'} onPress={()=>setShow(!show)}/>} />
 {show&&<Card><Text style={{fontSize:20,fontWeight:'900',color:colors.navy,marginBottom:12}}>Create admin account</Text><Field label="Name" value={name} onChangeText={setName}/><Field label="Email" value={email} onChangeText={setEmail} keyboardType="email-address"/><Field label="Temporary password" value={password} onChangeText={setPassword} secureTextEntry/><Select label="Role" value={role} onChange={setRole} options={roles}/><Button title="Create admin" onPress={create} disabled={!name.trim()||!email.trim()||password.length<8}/></Card>}
 {!items?<Loading label="Loading admin users…"/>:items.length===0?<Empty title="No staff accounts" message="Create your first admin account."/>:items.map(u=><Card key={api.idOf(u)}><View style={{flexDirection:'row',alignItems:'center',gap:12}}><View style={{flex:1}}><Text style={{fontWeight:'900',fontSize:17,color:colors.navy}}>{u.name}</Text><Text style={{color:colors.muted,marginTop:3}}>{u.email}</Text></View><Badge tone={u.role==='root_admin'?'purple':'pink'}>{u.role}</Badge><Badge tone={u.is_active?'green':'red'}>{u.is_active?'Active':'Disabled'}</Badge></View>{u.role!=='root_admin'&&<View style={{flexDirection:'row',gap:8,marginTop:12}}><Button title={u.is_active?'Disable':'Enable'} variant="secondary" onPress={()=>status(u)}/><Button title="Delete" variant="danger" onPress={()=>remove(u)}/></View>}</Card>)}
 </AppShell>;
}

pragma solidity ^0.8.0;

contract PrivateBank
{
    mapping (address => uint) balances;

    function GetBal() 
    public
    returns (uint) 
    {
        return balances[msg.sender];
    }

    uint public MinDeposit = 1 ether;

    Log TransferLog;

    constructor(address _lib)
    {
        TransferLog = Log(_lib);
    }

    function Deposit()
    public
    payable
    {
        if(msg.value >= MinDeposit)
        {
            balances[msg.sender]+=msg.value;
            TransferLog.AddMessage(msg.sender,msg.value,"Deposit");
        }
    }

    function CashOut(uint _am) public
    {
        if(_am<=balances[msg.sender])
        {

            (bool _callOk1, ) = msg.sender.call{value: _am}("");


            if (_callOk1)
            {
                balances[msg.sender]-=_am;
                TransferLog.AddMessage(msg.sender,_am,"CashOut");
            }
        }
    }

    receive() external payable {}    

}

contract Log 
{

    struct Message
    {
        address Sender;
        string  Data;
        uint Val;
        uint  Time;
    }

    Message[] public History;

    Message LastMsg;

    function AddMessage(address _adr,uint _val,string memory _data)
    public
    {
        LastMsg.Sender = _adr;
        LastMsg.Time = block.timestamp;
        LastMsg.Val = _val;
        LastMsg.Data = _data;
        History.push(LastMsg);
    }
}
